# Phase 6 baseline CVE disposition

All original high/critical records remain in baseline-full-scan.json.
OS findings: 38 package records / 13 CVEs; one additional HIGH record came from pip's embedded build SBOM.

| CVE | Severity | Baseline affected packages | Available baseline fix | Final disposition |
| --- | --- | --- | --- | --- |
| CVE-2023-45853 | CRITICAL | zlib1g | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2025-47273 | HIGH | setuptools | 78.1.1 | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2025-69720 | HIGH | libncursesw6, libtinfo6, ncurses-base, ncurses-bin | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2025-7458 | CRITICAL | libsqlite3-0 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-11822 | HIGH | libsqlite3-0 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-11824 | HIGH | libsqlite3-0 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-119373 | HIGH | libsqlite3-0 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-16742 | HIGH | libsystemd0, libudev1 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-41992 | HIGH | gzip | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-53613 | HIGH | bsdutils, libblkid1, libmount1, libsmartcols1, libuuid1, mount, util-linux, util-linux-extra | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-53615 | HIGH | bsdutils, libblkid1, libmount1, libsmartcols1, libuuid1, mount, util-linux, util-linux-extra | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-54369 | HIGH | libacl1 | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-78410 | HIGH | bsdutils, libblkid1, libmount1, libsmartcols1, libuuid1, mount, util-linux, util-linux-extra | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |
| CVE-2026-9538 | HIGH | perl-base | None published in Debian feed | Absent from final unfiltered scan after base replacement/tool removal |

See cve-analysis.json for every affected package/version, final replacement or absence, CVSS vector, references and exploitability context.
Ubuntu source-package backports/affectedness differ from Debian; numeric version comparison alone is not patch proof.
No scanner scope/severity/unfixed filtering, SBOM editing or vulnerability waiver was used.
