# Application integration

POLARIS-AI uses a React/Vite mission shell with OpenLayers for geospatial display and a
FastAPI scientific API. The browser reads `VITE_API_BASE_URL`, falling back locally to
`http://127.0.0.1:8000`.

The default Mission Control view combines only verified current products: OSI-SAF sea
ice, USNIC registry observations, the Bharati coordinate, and Natural Earth land.
A76C historical research is separated into Ice Intelligence and Model Lab views so it
cannot be mistaken for a current Bharati-region hazard.

Data flow for trajectory research is:

`USNIC observations + GLO12 analysis + ERA5 reanalysis -> FastAPI hindcast APIs -> Model Lab`

Frontend views never calculate scientific predictions. They render normalized backend
responses and show explicit loading/failure states without demonstration substitutes.
Sea-Ice Forecast and Navigation remain unavailable until real backend capabilities
exist.
