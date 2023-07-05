#include "KinematicsUtilities.h"

/* MRPtoDCM(q) returns the direction cosine matrix in terms of the 3x1 MRP vector q.
  @return UE::Math::TMatrix<double> direction cosine matrix
  @param FVector3d The MRP vector
 */
UE::Math::TMatrix<double> MRPtoDCM(FVector3d q) {
    auto rotationMatrix = UE::Math::TRotationMatrix<double>::Make(MRPtoQuaternion(q));
    return rotationMatrix;
}

/* MRPtoQuaternion(Q) translates the 3x1 MRP vector q into the Euler parameter (quaternion) vector.
  @return UE::Math::TQuat<double> quaternion vector
  @param FVector3d The MRP vector
 */
UE::Math::TQuat<double> MRPtoQuaternion(FVector3d q)
{
    double ps;
    ps = 1 + q.Dot(q);
    return UE::Math::TQuat<double>((1 - q.Dot(q)) / ps,
                2 * q[0] / ps,
                2 * q[1] / ps,
                2 * q[2] / ps);
}

/**
 * @brief RightQuat2LeftQuat(q) Maps right-handed quaternion q to left-handed quaternion
 * 
 * @param q The right-handed quaternion
 * @return UE::Math::TQuat<double> The left-handed quaternion
 */
UE::Math::TQuat<double> RightQuat2LeftQuat(FQuat q) 
{
  return UE::Math::TQuat<double>(q.W, -q.Y, -q.Z, q.X);
}

