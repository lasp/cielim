from test_harness import *

if __name__ == "__main__":

    file_dir = "../../../cielim/Content/FlybyData/bin/"
    file_name = input("What is the bin file to test (name only): ")
    
    file_handle = open(file_dir + file_name, "rb")

    message = delimited_protobuf.read(file_handle, cielimMessage_pb2.CielimMessage)

    output_name = file_name[:-4] + "_decoded.txt"

    with open(output_name, "w") as out_file:
        print(message, file=out_file)
