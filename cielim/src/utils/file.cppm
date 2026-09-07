// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Exports as a module basic file io functions. */

module;

#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <system_error>
#include <utility>
#include <vector>

export module cielim.utils:file;

import cielim.result;

export namespace cielim::utils::file
{

/**
 * @brief Reads the contents of a file and outputs into byte buffer.
 * @param file_path Path to the file to be read.
 * @return Vector containing the byte contents of the file.
 */
auto read_file(const std::filesystem::path& file_path) -> Result<std::vector<uint8_t>, std::error_code>
{
    std::error_code file_error;

    const std::filesystem::file_status file_status = std::filesystem::status(file_path, file_error);

    if (file_error)
        return Err(file_error);

    if (!std::filesystem::is_regular_file(file_status))
        return Err(std::make_error_code(std::errc::is_a_directory));

    const auto size = std::filesystem::file_size(file_path, file_error);

    if (file_error)
        return Err(file_error);

    constexpr auto MIN_STREAM_SIZE = static_cast<uintmax_t>(1); // Files shouldn't have zero or negative size
    constexpr auto MAX_STREAM_SIZE = static_cast<uintmax_t>(std::numeric_limits<std::streamsize>::max());

    if (size < MIN_STREAM_SIZE)
        return Err(std::make_error_code(std::errc::argument_out_of_domain));

    if (size > MAX_STREAM_SIZE)
        return Err(std::make_error_code(std::errc::file_too_large));

    std::ifstream file(file_path, std::ios::binary);

    if (!file)
        return Err(std::make_error_code(std::errc::io_error));

    std::vector<uint8_t> buffer(size);

    const auto read_size = static_cast<std::streamsize>(size);

    if (!file.read(reinterpret_cast<char*>(buffer.data()), read_size))
    {
        if (file.bad())
            return Err(std::make_error_code(std::errc::io_error));

        buffer.resize(file.gcount()); // Shrink buffer to EOF
    }

    return std::move(buffer);
}

/**
 * @brief Reads the contents of a file and outputs into 4-byte aligned buffer.
 * @param file_path Path to the file to be read.
 * @return Vector containing the 4-byte aligned contents of the file.
 */
auto read_file32(const std::filesystem::path& file_path) -> Result<std::vector<uint32_t>, std::error_code>
{
    const auto byte_buffer = read_file(file_path);

    if (!byte_buffer.has_value())
        return byte_buffer.propagate();

    if (byte_buffer.value().empty())
        return Err(std::make_error_code(std::errc::argument_out_of_domain));

    const size_t num_words = (byte_buffer.value().size() + 3) / 4; // Round up to nearest integer to avoid truncation

    std::vector<uint32_t> buffer(num_words, 0);

    std::memcpy(buffer.data(), byte_buffer.value().data(), byte_buffer.value().size());

    return std::move(buffer);
}

} // namespace cielim::utils::file
