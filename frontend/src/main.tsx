import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { AuditLog } from "./pages/AuditLog";
import { Benchmarking } from "./pages/Benchmarking";
import { CompanyAnalysis } from "./pages/CompanyAnalysis";
import { Dashboard } from "./pages/Dashboard";
import { RecordDetail } from "./pages/RecordDetail";
import { ReviewQueue } from "./pages/ReviewQueue";
import { UploadPage } from "./pages/UploadPage";
import "./styles.css";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to || (to !== "/" && location.pathname.startsWith(to));
  return (
    <Link to={to} className={isActive ? "active" : ""}>
      {children}
    </Link>
  );
}

function App() {
  return (
    <BrowserRouter>
      <nav className="top-nav">
        <Link to="/" className="nav-brand">
          <div className="nav-logo">FC</div>
          <span className="nav-title">
            Financial <span>Copilot</span>
          </span>
        </Link>
        <div className="nav-links">
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/analysis">Analysis</NavLink>
          <NavLink to="/upload">Upload</NavLink>
          <NavLink to="/review">Review</NavLink>
          <NavLink to="/benchmarking">Benchmark</NavLink>
          <NavLink to="/audit">Audit</NavLink>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analysis" element={<CompanyAnalysis />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/records/:id" element={<RecordDetail />} />
          <Route path="/benchmarking" element={<Benchmarking />} />
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
