import json

# scans byte buffer for complete json object
def scan_json(buffer):
    error = None
    if len(buffer) < 1: return (None, 0, error)
    l = 0
    while l < len(buffer) and buffer[l] != ord('{'):
        l += 1
    if l > 0:
        error = "garbage in json stream: "+repr(buffer[0:l])

    brackets = 1
    quote = False
    r = l + 1
    while r < len(buffer) and brackets > 0:
        if buffer[r] == ord('\\'):
            r += 2
            continue
        if quote:
            if buffer[r] == ord('"'):
                quote = False
        else:
            if buffer[r] == ord('"'):
                quote = True
            elif buffer[r] == ord('{'):
                brackets += 1
            elif buffer[r] == ord('}'):
                brackets -= 1
        r += 1
    if brackets == 0:
        req = json.loads(buffer[l:l+r].decode())
        return (req, l+r, error)
    return (None, l, error)
