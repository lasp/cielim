import os
import glob
from context import cielimMessage_pb2
import delimited_protobuf
import argparse

current_file_path = os.path.dirname(__file__)


def print_protobuffer_content(file_dir, file_name):
    file_path = file_dir + file_name

    with open(file_path, "rb") as file_handle:
        message = delimited_protobuf.read(file_handle, cielimMessage_pb2.CielimMessage)

    output_name = os.path.join(current_file_path, os.path.splitext(file_name)[0] + "_decoded.txt")

    with open(output_name, "w") as out_file:
        print(message, file=out_file)

    return output_name, message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print the contents of a Cielim protobuffer")
    parser.add_argument(
        "-f",
        "--filename",
        default=None,
        help="Protobuf file to print",
    )

    args = parser.parse_args()

    file_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))) + "/Content/FlybyData/bin/"
    test_dir = os.path.dirname(current_file_path) + "/support-data/protobufs/"

    if args.filename is not None:
        if os.path.exists(file_dir + args.filename):
            print_protobuffer_content(file_dir, args.filename)
        else:
            print_protobuffer_content(test_dir, args.filename)
    else:
        file_name = input("What is the bin file to print (name only): ")

        if os.path.exists(file_dir + file_name):
            print_protobuffer_content(file_dir, file_name)
        else:
            print_protobuffer_content(test_dir, file_name)
