// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Exports as a module basic spdlog logging functions with a convenient log init function. */

module;

#include <filesystem>
#include <memory>
#include <string>
#include <vector>

#include <fmt/ranges.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

export module cielim.utils.log;

constexpr int DEFAULT_FILE_SIZE = 5 * 1024 * 1024;

export namespace fmt
{
using fmt::join;
} // namespace fmt

export namespace cielim::utils::log
{

// Re-export spdlog global logging functions

using spdlog::critical;
using spdlog::debug;
using spdlog::error;
using spdlog::info;
using spdlog::trace;
using spdlog::warn;

using spdlog::flush_on;
using spdlog::get;
using spdlog::set_level;
using spdlog::set_pattern;

using level = spdlog::level::level_enum;

/**
 * @brief Initializes and registers a log with color console sink and optional file sink, and sets as default.
 * This function should not be used outside program start.
 * @param name Name of the logger.
 * @param file_path (Optional) Path to log file including name, e.g., logs/myapp.log.
 * No log file will be used if empty.
 * @param max_file_size (Optional) Number of characters after which new log file is created.
 * @param max_files (Optional) Max number of log files to write.
 */
auto init_log(
    const std::string& name,
    const std::filesystem::path& file_path = "",
    std::size_t max_file_size = DEFAULT_FILE_SIZE,
    std::size_t max_files = 2
) -> void
{
    std::vector<spdlog::sink_ptr> sinks;

    // Always include a color console output sink
    sinks.push_back(std::make_shared<spdlog::sinks::stdout_color_sink_mt>());

    if (!file_path.empty())
    {
        sinks.push_back(
            std::make_shared<spdlog::sinks::rotating_file_sink_mt>(file_path.string(), max_file_size, max_files)
        );
    }

    const auto logger = std::make_shared<spdlog::logger>(name, sinks.begin(), sinks.end());

    spdlog::register_logger(logger);
    spdlog::set_default_logger(logger);
}

} // namespace cielim::utils::log
