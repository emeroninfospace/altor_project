"""Pack the dashboard sources into the Custom HTML Block fixture.

    python3 dashboards/build.py

Each block = <name>.html + kit.css (style) + kit.js + <name>.js (script).
Run `bench --site <site> migrate` afterwards to load the fixture.
"""

import json
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "..", "altor_project", "fixtures", "custom_html_block.json")
BLOCKS = {
	"Project Overview Dashboard": "project",
	"HR Dashboard": "hr",
	"Stock Overview Dashboard": "stock",
	"Accounts Overview Dashboard": "accounts",
}


def read(name):
	with open(os.path.join(HERE, name), encoding="utf-8") as f:
		return f.read()


def main():
	with open(FIXTURE, encoding="utf-8") as f:
		blocks = json.load(f)
	by_name = {b["name"]: b for b in blocks}
	style, kit = read("kit.css"), read("kit.js")
	modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
	for name, src in BLOCKS.items():
		block = by_name.get(name) or {"doctype": "Custom HTML Block", "name": name, "docstatus": 0, "private": 0, "roles": []}
		block.update(html=read(f"{src}.html"), style=style, script=kit + "\n" + read(f"{src}.js"), modified=modified)
		if name not in by_name:
			blocks.append(block)
	with open(FIXTURE, "w", encoding="utf-8") as f:
		json.dump(blocks, f, indent=1, ensure_ascii=False)
		f.write("\n")
	print("Updated", ", ".join(BLOCKS))


if __name__ == "__main__":
	main()
