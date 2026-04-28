import React from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <MemoryRouter initialEntries={["/home"]} initialIndex={0}>
      <App />
    </MemoryRouter>
  </React.StrictMode>,
);
