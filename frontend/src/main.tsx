import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AuditLog } from "./pages/AuditLog";
import { RecordDetail } from "./pages/RecordDetail";
import { ReviewQueue } from "./pages/ReviewQueue";
import { UploadPage } from "./pages/UploadPage";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <nav className="top-nav">
        <span className="nav-title">Financial Data Autopilot</span>
        <div className="nav-links">
          <Link to="/">Upload</Link>
          <Link to="/review">Review</Link>
          <Link to="/audit">Audit</Link>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/records/:id" element={<RecordDetail />} />
          <Route path="/audit" element={<AuditLog />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
