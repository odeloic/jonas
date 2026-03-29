import { BrowserRouter, Route, Routes } from "react-router-dom";
import NavBar from "./components/NavBar";
import Home from "./pages/Home";
import Grammar from "./pages/Grammar";
import Vocabulary from "./pages/Vocabulary";
import Assignments from "./pages/Assignments";
import AssignmentDetail from "./pages/AssignmentDetail";
import AssignmentResults from "./pages/AssignmentResults";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-neutral-50">
        <NavBar />
        <main className="mx-auto max-w-2xl px-6 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/grammar" element={<Grammar />} />
            <Route path="/vocabulary" element={<Vocabulary />} />
            <Route path="/assignments" element={<Assignments />} />
            <Route path="/assignments/:id" element={<AssignmentDetail />} />
            <Route
              path="/assignments/:id/results/:submissionId"
              element={<AssignmentResults />}
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
