//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FCenBrightReduce class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CenBrightReduce.h"
IMPLEMENT_GLOBAL_SHADER(FCenBrightReduce, "/CielimShaders/CenBrightReduce.usf", "MainCS", SF_Compute);
