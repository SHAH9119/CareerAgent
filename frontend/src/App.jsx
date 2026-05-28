import { useState } from "react";
import { AgentRun } from "./pages/AgentRun";
import { Dashboard } from "./pages/Dashboard";
import { Onboarding } from "./pages/Onboarding";
import { Settings } from "./pages/Settings";
import { Tailoring } from "./pages/Tailoring";
import "./styles/theme.css";

const NAV_TO_PAGE = {
  pipeline: "dashboard",
  intelligence: "agent-run",
  resumes: "tailoring",
  settings: "settings",
};

const PAGE_TO_NAV = {
  dashboard: "pipeline",
  "agent-run": "intelligence",
  tailoring: "resumes",
  settings: "settings",
  onboarding: "pipeline",
};

export default function App() {
  const [page, setPage] = useState("dashboard");

  const activeNav = PAGE_TO_NAV[page] || "pipeline";

  const handleNav = (navId) => {
    const nextPage = NAV_TO_PAGE[navId];
    if (nextPage) setPage(nextPage);
  };

  const shellProps = {
    activeNav,
    onNav: handleNav,
    onProfileClick: () => setPage("onboarding"),
    onNewRun: () => setPage("agent-run"),
    onBack: () => setPage("dashboard"),
  };

  switch (page) {
    case "onboarding":
      return <Onboarding onComplete={() => setPage("dashboard")} />;
    case "agent-run":
      return <AgentRun {...shellProps} />;
    case "tailoring":
      return <Tailoring {...shellProps} />;
    case "settings":
      return <Settings {...shellProps} />;
    case "dashboard":
    default:
      return <Dashboard {...shellProps} />;
  }
}
