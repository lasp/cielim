//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FCoverageReduce class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CoverageReduce.h"
IMPLEMENT_GLOBAL_SHADER(FCoverageReduce, "/CielimShaders/CoverageReduce.usf", "MainCS", SF_Compute);
