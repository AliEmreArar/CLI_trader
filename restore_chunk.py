import os

SRC = '/mnt/ab-scratch/.ab-019cc8f7-a666-7703-9dd0-d9bb60b48ce9-a/upper/data/bist_model_ready.db'
DST = 'data/bist_model_ready.db'

try:
    if os.path.exists(DST):
        os.remove(DST)
        
    with open(SRC, 'rb') as fsrc:
        with open(DST, 'wb') as fdst:
            while True:
                buf = fsrc.read(1024*1024)
                if not buf:
                    break
                fdst.write(buf)
    print("Restore complete.")
except Exception as e:
    print(f"Error: {e}")
