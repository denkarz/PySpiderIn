def secret(string):
    if string is None:
        return ''
    else:
        return '*' * len(string)
