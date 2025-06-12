#pragma once

#include "Math/Matrix.h"
#include "Math/Quat.h"
#include "Math/Vector.h"

UE::Math::TMatrix<double> MRPtoDCM(const FVector3d& q);
UE::Math::TQuat<double> MRPtoQuaternion(const FVector3d& v);
UE::Math::TVector<double> QuaterniontoMRP(const FQuat& q);
UE::Math::TQuat<double> RightQuat2LeftQuat(const FQuat& q);
UE::Math::TVector<double> Right2LeftVector(const FVector3d& v);
