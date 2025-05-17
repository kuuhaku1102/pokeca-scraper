 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/README.md
index 0000000..74958a1 100644
--- a//dev/null
+++ b/README.md
@@ -0,0 +1,6 @@
+# Pokeca Scraper
+
+This repository contains various scrapers for Pokémon card information.
+
+[![.github/workflows/scrape_ciel.yml](https://github.com/kuuhaku1102/pokeca-scraper/actions/workflows/scrape_ciel.yml/badge.svg)](https://github.com/kuuhaku1102/pokeca-scraper/actions/workflows/scrape_ciel.yml)
+
 
EOF
)
