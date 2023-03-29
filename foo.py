import tempfile
    

def write_hello_file(file_path:str) -> None:
    print(f"{file_path=}")
    with open(file_path, mode="w") as f:
        f.write("hello")

        
with tempfile.NamedTemporaryFile() as f:
    write_hello_file(f.name)
