import { BrowserRouter, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Assignments from "./pages/Assignments";
import AssignmentDetail from "./pages/AssignmentDetail";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <main className="mx-auto max-w-lg px-4 py-6">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/assignments" element={<Assignments />} />
            <Route path="/assignments/:id" element={<AssignmentDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
