import os
import glob
from context import cielimMessage_pb2
import delimited_protobuf

current_file_path = os.path.dirname(__file__)


def print_protobuffer_content():
    file_dir = os.path.join(current_file_path, "../../../Content/FlybyData/bin/")
    file_name = "bennu_image.bin"
    file_path = os.path.join(file_dir, file_name)

    with open(file_path, "rb") as file_handle:
        message = delimited_protobuf.read(file_handle, cielimMessage_pb2.CielimMessage)

    output_name = os.path.join(current_file_path, os.path.splitext(file_name)[0] + "_decoded.txt")

    with open(output_name, "w") as out_file:
        print(message, file=out_file)

    return output_name, message


if __name__ == "__main__":
    print_protobuffer_content()
