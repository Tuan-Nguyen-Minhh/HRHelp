import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { AppRouter } from "@/app/router";
import "@/index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Thiếu #root.");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </BrowserRouter>
  </StrictMode>,
);
