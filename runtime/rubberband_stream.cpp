// Local development diagnostic, not a production backend. No gain, clipping,
// padding, trimming, marker alignment, key-frame map, or encoder is applied.
#include "rubberband/RubberBandStretcher.h"
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>
#include <sys/stat.h>
#include <CommonCrypto/CommonDigest.h>
#include <sstream>
#include <iomanip>
#include <sys/resource.h>
#include <chrono>

using Stretcher = RubberBand::RubberBandStretcher;

static unsigned parseUnsigned(const char *s) {
    std::string t(s);
    if (t.empty() || t.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("Expected a positive integer");
    const auto n = std::stoull(t);
    if (!n || n > std::numeric_limits<unsigned>::max())
        throw std::runtime_error("Integer outside supported range");
    return static_cast<unsigned>(n);
}

static void writeAll(int fd, const float *data, size_t count) {
    const char *p = reinterpret_cast<const char *>(data);
    size_t bytes = count * sizeof(float);
    while (bytes) {
        const auto n = ::write(fd, p, bytes);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) throw std::runtime_error("Output write failed");
        p += n;
        bytes -= static_cast<size_t>(n);
    }
}

static std::string digest(CC_SHA256_CTX ctx) {
    unsigned char bytes[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Final(bytes, &ctx);
    std::ostringstream out;
    for (auto byte : bytes) out << std::hex << std::setfill('0') << std::setw(2) << unsigned(byte);
    return out.str();
}
static bool same(const struct stat &a, const struct stat &b) {
    return a.st_dev == b.st_dev && a.st_ino == b.st_ino && a.st_size == b.st_size &&
           a.st_mtimespec.tv_sec == b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec == b.st_mtimespec.tv_nsec &&
           a.st_ctimespec.tv_sec == b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec == b.st_ctimespec.tv_nsec;
}
static struct stat checkedStat(int fd) {
    struct stat s;
    if (fstat(fd, &s)) throw std::runtime_error("Input fstat failed");
    return s;
}
static void readExact(int fd, float *data, size_t bytes, CC_SHA256_CTX &sha) {
    char *p = reinterpret_cast<char *>(data);
    while (bytes) {
        ssize_t n = read(fd, p, bytes);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) throw std::runtime_error("Input short read or IO error");
        CC_SHA256_Update(&sha, p, static_cast<CC_LONG>(n));
        p += n; bytes -= static_cast<size_t>(n);
    }
}
static void requireEOF(int fd) {
    char c; ssize_t n;
    do { n = read(fd, &c, 1); } while (n < 0 && errno == EINTR);
    if (n != 0) throw std::runtime_error("Input grew or EOF read failed");
}
int main(int argc, char **argv) {
    const auto started = std::chrono::steady_clock::now();
    int fd = -1, inputFd = -1;
    const char *phase = "preflight";
    size_t studyFrames = 0, processFrames = 0, outputFrames = 0;
    try {
        if (argc == 2 && std::string(argv[1]) == "--describe") {
            std::cout << "{\"helper\":\"rubberband-offline-f32-stream/5\","
                         "\"library_source_release\":\"4.0.0\","
                         "\"input\":\"interleaved f32le\","
                         "\"output\":\"interleaved f32le; no helper gain/clipping; backend may change peaks\","
                         "\"mode\":\"offline\",\"engine_requested\":3,"
                         "\"io_strategy\":\"two-pass-seekable-f32\",\"dsp_executed\":false}\n";
            return 0;
        }
        if (argc != 6) throw std::runtime_error(
            "Usage: probe INPUT.f32le OUTPUT.f32le RATE CHANNELS TIME_RATIO_BINARY64");
        static_assert(sizeof(float) == 4, "Requires float32");
        static_assert(std::numeric_limits<float>::is_iec559, "Requires IEEE float");
        const uint16_t endian = 1;
        if (*reinterpret_cast<const uint8_t *>(&endian) != 1)
            throw std::runtime_error("This diagnostic requires a little-endian host");
        const unsigned rate = parseUnsigned(argv[3]);
        const unsigned channels = parseUnsigned(argv[4]);
        size_t consumed = 0;
        const std::string ratioText(argv[5]);
        const double timeRatio = std::stod(ratioText, &consumed);
        if (consumed != ratioText.size() || !std::isfinite(timeRatio) ||
            timeRatio < 0.5 || timeRatio > 2.0)
            throw std::runtime_error("Supported time ratio interval is 0.5 through 2");
        if (rate != 48000 || (channels != 1 && channels != 2))
            throw std::runtime_error("Scope is 48kHz mono/stereo");
        inputFd = ::open(argv[1], O_RDONLY | O_NOFOLLOW);
        if (inputFd < 0) throw std::runtime_error("Input could not be opened");
        const struct stat initial = checkedStat(inputFd);
        if (!S_ISREG(initial.st_mode) || initial.st_size <= 0 || initial.st_size % (4 * channels))
            throw std::runtime_error("Invalid regular PCM input");
        const uint64_t count = uint64_t(initial.st_size) / (4 * channels);
        if (count >= (uint64_t(1) << 51) || count > std::numeric_limits<size_t>::max() / (8 * channels))
            throw std::runtime_error("Input frame count outside numeric range");
        const size_t frames = static_cast<size_t>(count);
        const double target = static_cast<double>(frames) * timeRatio;
        if (target >= double(uint64_t(1) << 52)) throw std::runtime_error("Output target outside binary64 range");
        const size_t expectedFrames = static_cast<size_t>(std::round(target));
        CC_SHA256_CTX studySHA, processSHA, outputSHA;
        CC_SHA256_Init(&studySHA); CC_SHA256_Init(&processSHA); CC_SHA256_Init(&outputSHA);

        constexpr size_t block = 4096;
        const int options = Stretcher::OptionProcessOffline |
                            Stretcher::OptionEngineFiner |
                            Stretcher::OptionChannelsTogether |
                            Stretcher::OptionThreadingNever;
        Stretcher rb(rate, channels, options,
                     timeRatio, 1.0);
        if (rb.getEngineVersion() != 3) throw std::runtime_error("R3 engine unavailable");
        rb.setExpectedInputDuration(frames);
        rb.setMaxProcessSize(block);
        std::vector<float> inputBlock(block * channels);
        std::vector<std::vector<float>> source(channels, std::vector<float>(block));
        std::vector<const float *> inPointers(channels);
        for (unsigned c = 0; c < channels; ++c) inPointers[c] = source[c].data();
        auto fill = [&](size_t n, CC_SHA256_CTX &sha) {
            readExact(inputFd, inputBlock.data(), n * channels * 4, sha);
            for (size_t f = 0; f < n; ++f) for (unsigned c = 0; c < channels; ++c) {
                float v = inputBlock[f * channels + c];
                if (!std::isfinite(v)) throw std::runtime_error("Nonfinite input PCM");
                source[c][f] = v;
            }
        };
        phase = "study";
        for (size_t start = 0; start < frames; start += block) {
            const size_t n = std::min(block, frames - start);
            fill(n, studySHA); studyFrames += n;
            rb.study(inPointers.data(), n, start + n == frames);
        }

        requireEOF(inputFd);
        const struct stat between = checkedStat(inputFd);
        if (!same(initial, between) || lseek(inputFd, 0, SEEK_SET) != 0)
            throw std::runtime_error("Input changed or rewind failed");
        const std::string studyHash = digest(studySHA);
        phase = "process";
        fd = ::open(argv[2], O_WRONLY | O_CREAT | O_EXCL, 0600);
        if (fd < 0) throw std::runtime_error("Output must be a new writable file");
        std::vector<std::vector<float>> output(channels, std::vector<float>(block));
        std::vector<float *> outPointers(channels);
        for (unsigned c = 0; c < channels; ++c) outPointers[c] = output[c].data();
        std::vector<float> interleaved(block * channels);
        size_t outOfUnit = 0, nonFinite = 0;
        double peak = 0.0;
        auto drain = [&]() {
            while (rb.available() > 0) {
                const size_t n = rb.retrieve(outPointers.data(),
                    std::min(block, static_cast<size_t>(rb.available())));
                if (!n) throw std::runtime_error("Available output could not be retrieved");
                for (size_t f = 0; f < n; ++f) {
                    for (unsigned c = 0; c < channels; ++c) {
                        const float value = output[c][f];
                        interleaved[f * channels + c] = value;
                        if (!std::isfinite(value)) ++nonFinite;
                        else {
                            peak = std::max(peak, std::abs(static_cast<double>(value)));
                            if (std::abs(value) > 1.0f) ++outOfUnit;
                        }
                    }
                }
                writeAll(fd, interleaved.data(), n * channels);
                CC_SHA256_Update(&outputSHA, interleaved.data(), static_cast<CC_LONG>(n * channels * 4));
                outputFrames += n;
            }
        };
        for (size_t start = 0; start < frames; start += block) {
            const size_t n = std::min(block, frames - start);
            fill(n, processSHA); processFrames += n;
            rb.process(inPointers.data(), n, start + n == frames);
            drain();
        }
        const int terminalAvailable = rb.available();
        phase = "verify";
        requireEOF(inputFd);
        const struct stat after = checkedStat(inputFd);
        struct stat pathAfter;
        if (stat(argv[1], &pathAfter) || !same(initial, between) || !same(initial, after) || !same(initial, pathAfter))
            throw std::runtime_error("Input identity changed");
        const std::string processHash = digest(processSHA);
        if (studyFrames != frames || processFrames != frames || studyHash != processHash)
            throw std::runtime_error("Actual pass bytes differ");
        struct stat outputStat;
        if (fstat(fd, &outputStat) || uint64_t(outputStat.st_size) != uint64_t(outputFrames) * channels * 4)
            throw std::runtime_error("Output write count differs");
        const int outputClose = ::close(fd); fd = -1;
        if (outputClose) throw std::runtime_error("Output close failed");
        const int inputClose = ::close(inputFd); inputFd = -1;
        if (inputClose) throw std::runtime_error("Input close failed");
        struct rusage usage;
        if (getrusage(RUSAGE_SELF, &usage)) throw std::runtime_error("Resource usage unavailable");
        const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
        std::cout.precision(17);
        std::cout << "{\"helper\":\"rubberband-offline-f32-stream/5\","
                  << "\"io_strategy\":\"two-pass-seekable-f32\","
                  << "\"study_frames\":" << studyFrames << ",\"process_frames\":" << processFrames
                  << ",\"study_bytes\":" << studyFrames * channels * 4 << ",\"process_bytes\":" << processFrames * channels * 4
                  << ",\"study_sha256\":\"" << studyHash << "\",\"process_sha256\":\"" << processHash << "\""
                  << ",\"output_sha256\":\"" << digest(outputSHA) << "\""
                  << ",\"input_device\":" << initial.st_dev << ",\"input_inode\":" << initial.st_ino
                  << ",\"input_bytes\":" << initial.st_size << ",\"input_stat_three_passes_match\":true"
                  << ",\"helper_peak_rss_bytes_macos\":" << usage.ru_maxrss << ",\"helper_elapsed_seconds\":" << elapsed
                  << ",\"engine\":" << rb.getEngineVersion()
                  << ",\"option_bits\":" << options
                  << ",\"sample_rate\":" << rate << ",\"channels\":" << channels
                  << ",\"input_frames\":" << frames
                  << ",\"time_ratio\":" << rb.getTimeRatio()
                  << ",\"pitch_scale\":" << rb.getPitchScale()
                  << ",\"block_frames\":" << block
                  << ",\"expected_frames\":" << expectedFrames
                  << ",\"actual_frames\":" << outputFrames
                  << ",\"terminal_available\":" << terminalAvailable
                  << ",\"peak\":" << peak << ",\"out_of_unit_samples\":" << outOfUnit
                  << ",\"non_finite_samples\":" << nonFinite
                  << ",\"helper_gain_applied\":false,\"helper_clipping_applied\":false,"
                     "\"helper_padding_applied\":false,\"helper_trimming_applied\":false,"
                     "\"backend_internal_start_and_target_handling\":true}\n";
        return terminalAvailable == -1 && outputFrames == expectedFrames && nonFinite == 0 ? 0 : 2;
    } catch (const std::exception &e) {
        if (fd >= 0) ::close(fd);
        if (inputFd >= 0) ::close(inputFd);
        std::cerr << "Diagnostic failed phase=" << phase << " study_frames=" << studyFrames << " process_frames=" << processFrames << " output_frames=" << outputFrames << ": " << e.what() << '\n';
        return 1;
    }
}
