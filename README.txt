Quantum Edge v30
================

Uruchomienie:

    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000

Przepływ analizy:

    DAP_RUNNING
      -> DAP_BLOCKED (FAIL/STOP)
      -> READY_FOR_ENGINE_1
      -> ENGINES_RUNNING
      -> READY_TO_SAVE
      -> COMPLETED

Wynik końcowy może zostać zapisany wyłącznie przez transakcyjną granicę w
qe_pipeline.py. Skan SELECT nie uruchamia DAP ani silników.

Konfiguracja środowiska:

    QE_DB_PATH            ścieżka SQLite (na hostingu ustaw trwały dysk)
    API_FOOTBALL_KEY      opcjonalny adapter API-Football
    SPORTMONKS_TOKEN      opcjonalny adapter Sportmonks

Testy:

    python -m unittest discover -s tests -v

Pełny raport: AUDIT_DAP_PIPELINE_2026-08-29.md
