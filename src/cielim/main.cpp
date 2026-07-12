// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Serves as the program entry point. */

import cielim.utils.log;

auto main() -> int
{
    // Create main log
    cielim::utils::log::InitLog("log-cielim");

    // Set global log format
    cielim::utils::log::set_pattern("[%Y-%m-%d %H:%M:%S.%e] %n - %^%l%$: %v");

    // Set lowest rendered level to trace i.e., everything is logged
    cielim::utils::log::set_level(cielim::utils::log::level::trace);

    // Flush warnings and above immediately instead of buffering
    cielim::utils::log::flush_on(cielim::utils::log::level::warn);

    cielim::utils::log::trace("This is a trace!");
    cielim::utils::log::debug("This is a debug!");
    cielim::utils::log::info("This is an info!");
    cielim::utils::log::warn("This is a warn!");
    cielim::utils::log::error("This is an error!");
    cielim::utils::log::critical("This is a critical!");

    // Force flush messages
    cielim::utils::log::get("log-cielim")->flush();

    return 0;
}
