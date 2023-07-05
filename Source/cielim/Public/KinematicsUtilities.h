#pragma once

#include "Math/Matrix.h"
#include "Math/Quat.h"
#include "Math/Vector.h"

UE::Math::TMatrix<double> MRPtoDCM(FVector3d q);
UE::Math::TQuat<double> MRPtoQuaternion(FVector3d q);
UE::Math::TQuat<double> RightQuat2LeftQuat(FQuat q);

