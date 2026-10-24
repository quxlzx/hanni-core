import { createRoot } from "react-dom/client";
import { App } from "./workspace";
import { Mini } from "./mini";
import "./style.css";
import { ChatApp } from "./chat_app";
createRoot(document.getElementById("app-root")!).render(
  new URLSearchParams(window.location.search).get("view") === "mini" ? (
    <Mini />
  ) : new URLSearchParams(window.location.search).get("view") ===
    "workspace" ? (
    <App />
  ) : (
    <ChatApp />
  ),
);
