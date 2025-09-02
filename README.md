
# CMR Report Builder (Streamlit) — v4.2

- Parser robusto per **export CVI** come nel file di esempio
- Inserimento automatico **valori paziente** + **v.n.** (sesso/età)
- Selettore **1,5T vs 3T (Philips 7700)** con **T1 nativo** adattato (**<1045 ms** per 1,5T; **1130–1300 ms** per 3T)

## Avvio
```bash
cd cmr_streamlit_app_v2
pip install streamlit pandas
streamlit run app_streamlit.py
```

Carica/incolla il testo dell'export CVI per ottenere il **referto**.
