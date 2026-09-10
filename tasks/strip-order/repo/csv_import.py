from normalise import clean_token


def tags_from_csv(line):
    return [clean_token(part) for part in line.split(",") if part.strip()]
