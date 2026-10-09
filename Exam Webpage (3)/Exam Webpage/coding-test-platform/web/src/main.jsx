import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { loadBackendConfig } from "./lib/api.js";
import "./styles.css";

// Find out where the API is before anything calls it
loadBackendConfig().finally(() => {
  createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
});
