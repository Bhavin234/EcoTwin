import { Route, BrowserRouter, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { LocationProvider } from "./context/LocationContext";
import Data from "./pages/Data";
import Impact from "./pages/Impact";
import InvestigationDetail from "./pages/InvestigationDetail";
import Investigations from "./pages/Investigations";
import Overview from "./pages/Overview";
import Resources from "./pages/Resources";

export default function App() {
  return (
    <LocationProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Overview />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/investigations" element={<Investigations />} />
            <Route path="/investigations/:anomalyId" element={<InvestigationDetail />} />
            <Route path="/impact" element={<Impact />} />
            <Route path="/data" element={<Data />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LocationProvider>
  );
}
