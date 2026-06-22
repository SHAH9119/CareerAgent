import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getMe, getToken, logout } from "./api/careerAgent";
import { LoadingSpinner } from "./components/LoadingSpinner";
import { AgentRun } from "./pages/AgentRun";
import { Auth } from "./pages/Auth";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { Onboarding } from "./pages/Onboarding";
import { Settings } from "./pages/Settings";
import { Tailoring } from "./pages/Tailoring";
import "./styles/theme.css";

const NAV_TO_PATH = {
  pipeline: "/dashboard",
  intelligence: "/agent-run",
  resumes: "/tailoring",
  settings: "/settings",
};

const PATH_TO_NAV = {
  "/dashboard": "pipeline",
  "/agent-run": "intelligence",
  "/tailoring": "resumes",
  "/settings": "settings",
  "/onboarding": "pipeline",
};

function ProtectedApp({ user, onLogout }) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeNav = PATH_TO_NAV[location.pathname] || "pipeline";

  const handleNav = (navId) => {
    const path = NAV_TO_PATH[navId];
    if (path) navigate(path);
  };

  const shellProps = {
    activeNav,
    onNav: handleNav,
    onProfileClick: () => navigate("/onboarding"),
    onNewRun: () => navigate("/agent-run"),
    onBack: () => navigate("/dashboard"),
    currentUser: user,
    onLogout: () => {
      logout();
      onLogout();
      navigate("/");
    },
  };

  return (
    <Routes>
      <Route path="/dashboard" element={<Dashboard {...shellProps} />} />
      <Route path="/agent-run" element={<AgentRun {...shellProps} />} />
      <Route path="/tailoring" element={<Tailoring {...shellProps} />} />
      <Route path="/settings" element={<Settings {...shellProps} />} />
      <Route path="/onboarding" element={<Onboarding onComplete={() => navigate("/dashboard")} />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  if (authLoading) {
    return <LoadingSpinner label="Loading CareerAgent..." />;
  }

  return (
    <Routes>
      <Route
        path="/"
        element={user ? <Navigate to="/dashboard" replace /> : <Landing />}
      />
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" replace /> : <Auth mode="login" onAuthed={setUser} />}
      />
      <Route
        path="/signup"
        element={user ? <Navigate to="/dashboard" replace /> : <Auth mode="signup" onAuthed={setUser} />}
      />
      <Route
        path="/*"
        element={
          user ? (
            <ProtectedApp user={user} onLogout={() => setUser(null)} />
          ) : (
            <Navigate to="/login" replace state={{ from: window.location.pathname }} />
          )
        }
      />
    </Routes>
  );
}
