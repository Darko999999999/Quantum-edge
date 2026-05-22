# Quantum Edge Web MVP

Pierwsza wersja prywatnej aplikacji webowej na telefon.

## Uruchomienie

1. Rozpakuj folder.
2. W terminalu w folderze projektu wpisz:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

3. Otwórz w przeglądarce:

```text
http://127.0.0.1:8000
```

Na telefonie w tej samej sieci Wi-Fi można wejść przez adres IP komputera, np.:

```text
http://192.168.1.20:8000
```

## Co już działa

- formularz analizy meczu
- model probability/value
- exact score
- chaos risk
- historia analiz w SQLite
- wygląd mobilny

## Następny etap

- automatyczne pobieranie danych z SofaScore / Understat
- skaner meczów
- tracker bankrollu
