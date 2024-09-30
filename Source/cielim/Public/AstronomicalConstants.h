/*
 Copyright (c) 2014, University of Colorado at Boulder

 Permission to use, copy, modify, and/or distribute this software for any
 purpose with or without fee is hereby granted, provided that the above
 copyright notice and this permission notice appear in all copies.
*/

#ifndef ASTRONOMICAL_CONSTANTS_H
#define ASTRONOMICAL_CONSTANTS_H

#include <math.h>

// universial Gravitational Constant, units are in km^3/s^2/kg
#define G_UNIVERSIAL 6.67259e-20
// astronomical unit in units of kilometers
#define AU 149597870.693
// [m/s] convert astronomical unit to kilometers
#define SPEED_LIGHT 299792458.0
// [W/m^2] solar flux at earth
#define SOLAR_FLUX_EARTH 1372.5398
#define EARTH_GRAV 9.80665
#define D2R (M_PI/180.0)

// Gravitational Constants mu = G*m, where m is the planet of the attracting planet.
// All units are km^3/s^2.
// Values are obtained from SPICE kernels in http://naif.jpl.nasa.gov/pub/naif/generic_kernels/
#define MU_SUN 132712440023.310
#define MU_MERCURY 22032.080
#define MU_VENUS 324858.599
#define MU_EARTH 398600.436
#define MU_MOON 4902.799
#define MU_MARS 42828.314
#define MU_JUPITER 126712767.881
#define MU_SATURN 37940626.068
#define MU_URANUS 5794559.128
#define MU_NEPTUNE 6836534.065
#define MU_PLUTO 983.055

/* planet information for major solar system bodies. Units are in km.
 * data taken from http://nssdc.gsfc.nasa.gov/planetary/planets.html
 */

// Sun km
#define REQ_SUN 695000.0

// Mercury
#define REQ_MERCURY 2439.7 // km 
#define J2_MERCURY 60.0e-6
#define SMA_MERCURY 0.38709893*AU
#define I_MERCURY 7.00487*D2R
#define E_MERCURY 0.20563069
#define OMEGA_MERCURY (2*M_PI/1407.6/3600.0) // planetary rotation rate, rad/sec

// Venus
#define REQ_VENUS 6051.8 // km
#define J2_VENUS 4.458e-6
#define SMA_VENUS 0.72333199*AU
#define I_VENUS 3.39471*D2R
#define E_VENUS 0.00677323
#define OMEGA_VENUS (2*M_PI/(-5832.6)/3600.0) // planetary rotation rate, rad/sec

// Earth
#define REQ_EARTH 6378.1366 // km, from SPICE
#define RP_EARTH 6356.7519 // km, from SPICE
#define J2_EARTH 1082.616e-6
#define J3_EARTH -2.53881e-6
#define J4_EARTH -1.65597e-6
#define J5_EARTH -0.15e-6
#define J6_EARTH 0.57e-6
#define SMA_EARTH 1.00000011*AU
#define I_EARTH 0.00005*D2R
#define E_EARTH 0.01671022
#define OMEGA_EARTH (2*M_PI/23.9345/3600.0) // planetary rotation rate, rad/sec

// Moon
#define REQ_MOON 1737.4
#define J2_MOON 202.7e-6
#define SMA_MOON 0.3844e6
#define E_MOON 0.0549
#define OMEGA_MOON (2*M_PI/655.728/3600.0) // rotation rate, rad/sec

// Mars
#define REQ_MARS 3396.19 // km
#define RP_MARS 3376.2 // km
#define J2_MARS 1960.45e-6
#define SMA_MARS 1.52366231*AU
#define I_MARS 1.85061*D2R
#define E_MARS 0.09341233
#define OMEGA_MARS (2*M_PI/24.6229/3600.0) // polar rotation rate, rad/sec

// Phobos
#define REQ_PHOBOS 11.2 // km

// Deimos
#define REQ_DEIMOS 6.1 // km

// Jupiter
#define REQ_JUPITER 71492.0
#define J2_JUPITER 14736.0e-6
#define SMA_JUPITER 5.20336301*AU
#define I_JUPITER 1.30530*D2R
#define E_JUPITER 0.04839266
#define OMEGA_JUPITER (2*M_PI/9.9250/3600.0) // Jupiter's polar rotation rate, rad/sec

// Saturn
#define REQ_SATURN 60268.0
#define J2_SATURN 16298.e-6
#define SMA_SATURN 9.53707032*AU
#define I_SATURN 2.48446*D2R
#define E_SATURN 0.05415060
#define OMEGA_SATURN (2*M_PI/10.656/3600.0) // polar rotation rate, rad/sec

// Uranus
#define REQ_URANUS 25559.0
#define J2_URANUS 3343.43e-6
#define SMA_URANUS 19.19126393*AU
#define I_URANUS 0.76986*D2R
#define E_URANUS 0.04716771
#define OMEGA_URANUS (2*M_PI/(-17.24)/3600.0) // polar rotation rate, rad/sec

// Neptune
#define REQ_NEPTUNE 24746.0
#define J2_NEPTUNE 3411.e-6
#define SMA_NEPTUNE 30.06896348*AU
#define I_NEPTUNE 1.76917*D2R
#define E_NEPTUNE 0.00858587
#define OMEGA_NEPTUNE (2*M_PI/16.11/3600.0) // polar rotation rate, rad/sec

// Pluto
#define REQ_PLUTO 1137.0
#define SMA_PLUTO 39.48168677*AU
#define I_PLUTO 17.14175*D2R
#define E_PLUTO 0.24880766
#define OMEGA_PLUTO (2*M_PI/(-153.2928)/3600.0) // polar rotation rate, rad/sec

#endif // ASTRONOMICAL_CONSTANTS_H