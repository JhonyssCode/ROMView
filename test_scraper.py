from scraper import ROMScraper
s = ROMScraper()
r = s.browse("Game Boy Advance")
print(f"{len(r)} ROMs encontradas.")
for x in r[:5]:
    print(f"  - {x['name']} ({x['downloads']} downloads)")
