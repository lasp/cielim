// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Exports as a module basic file io functions. */

module;

#include <expected>
#include <filesystem>
#include <fstream>
#include <system_error>
#include <vector>

export module cielim.utils.file;

export namespace cielim::utils::file
{

/**
 * @brief Reads the contents of a file and outputs into byte buffer.
 * @param file_path Path to the file to be read.
 * @return Vector containing the byte contents of the file.
 */
[[nodiscard]] auto read_file(const std::filesystem::path& file_path)
    -> std::expected<std::vector<uint8_t>, std::error_code>
{
    std::error_code file_error;

    const std::filesystem::file_status file_status = std::filesystem::status(file_path, file_error);

    if (file_error)
        return std::unexpected(file_error);

    if (!std::filesystem::is_regular_file(file_status))
        return std::unexpected(std::make_error_code(std::errc::is_a_directory));

    const auto size = std::filesystem::file_size(file_path, file_error);

    if (file_error)
        return std::unexpected(file_error);

    constexpr auto MIN_STREAM_SIZE = static_cast<uintmax_t>(1); // Files shouldn't have zero or negative size
    constexpr auto MAX_STREAM_SIZE = static_cast<uintmax_t>(std::numeric_limits<std::streamsize>::max());

    if (size < MIN_STREAM_SIZE)
        return std::unexpected(std::make_error_code(std::errc::argument_out_of_domain));

    if (size > MAX_STREAM_SIZE)
        return std::unexpected(std::make_error_code(std::errc::file_too_large));

    std::ifstream file(file_path, std::ios::binary);

    if (!file)
        return std::unexpected(std::make_error_code(std::errc::io_error));

    std::vector<uint8_t> buffer(size);

    const auto read_size = static_cast<std::streamsize>(size);

    if (!file.read(reinterpret_cast<char*>(buffer.data()), read_size))
    {
        if (file.bad())
            return std::unexpected(std::make_error_code(std::errc::io_error));

        buffer.resize(file.gcount()); // Shrink buffer to EOF
    }

    return buffer;
}

/**
 * @brief Reads the contents of a file and outputs into 4-byte aligned buffer.
 * @param file_path Path to the file to be read.
 * @return Vector containing the 4-byte aligned contents of the file.
 */
[[nodiscard]] auto read_file32(const std::filesystem::path& file_path)
    -> std::expected<std::vector<uint32_t>, std::error_code>
{
    const auto byte_buffer = read_file(file_path);

    if (!byte_buffer.has_value())
        return std::unexpected(byte_buffer.error());

    if (byte_buffer->empty())
        return std::unexpected(std::make_error_code(std::errc::argument_out_of_domain));

    const size_t num_words = (byte_buffer->size() + 3) / 4; // Round up to nearest integer to avoid truncation

    std::vector<uint32_t> buffer(num_words, 0);

    std::memcpy(buffer.data(), byte_buffer->data(), byte_buffer->size());

    return buffer;
}

} // namespace cielim::utils::file
