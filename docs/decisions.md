\# Design Decisions



\## 2026-10-14: Don't commit data files

\- \*\*What:\*\* data/raw/ and data/processed/ are in .gitignore.

\- \*\*Why:\*\* Raw HTML is large and is UFCStats' content, not mine. Processed data can be regenerated from code, so committing it risks a stale copy that doesn't match the code.

\- \*\*Alternatives considered:\*\* Committing processed data so others can skip scraping (rejected for now), or Git LFS for large files.



\## 2026-10-14: Use a Python virtual environment (venv)

\- \*\*What:\*\* All project libraries are installed into a project-local `.venv`, with exact versions pinned in `requirements.txt`.

\- \*\*Why:\*\* Reproducibility and isolation. Anyone can rebuild the exact environment with `pip install -r requirements.txt`, and upgrading a library for another project can't break this one.

\- \*\*Alternatives considered:\*\* Installing globally (no isolation, can't reproduce versions) and conda (more powerful, but unnecessary for a pure-Python project).

