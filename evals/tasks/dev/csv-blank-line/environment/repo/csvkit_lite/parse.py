def parse_rows(text: str) -> list[tuple[str, int]]:
    rows = []
    for line in text.splitlines():
        parts = line.split(",")
        rows.append((parts[0].strip(), int(parts[1])))
    return rows
