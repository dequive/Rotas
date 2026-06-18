import pathlib, json
data = json.loads(pathlib.Path(r"c:/Users/Quive/OneDrive/Documents/Rotas/summary_data.json").read_text(encoding="utf-8"))
out = pathlib.Path(r"c:/Users/Quive/OneDrive/Documents/Rotas/.planning/research/SUMMARY.md")
out.write_text(data["content"], encoding="utf-8")
print("Written", out.stat().st_size, "bytes")
