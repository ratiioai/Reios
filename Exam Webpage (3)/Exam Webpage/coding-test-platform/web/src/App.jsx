import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireRole, useAuth } from "./lib/auth.jsx";
import { ConfirmHost, Loading, ToastHost } from "./components/ui.jsx";
import { homeFor } from "./lib/api.js";

import Login from "./pages/Login.jsx";
import Console from "./pages/admin/Console.jsx";
import StudentDashboard from "./pages/student/Dashboard.jsx";

// The code editor is most of the bundle, and only the exam page needs it.
// A tab opened before a new deploy asks for a chunk that no longer exists; reload once to pick up
// the new build instead of leaving a blank page.
const RELOAD_FLAG = "reios_chunk_reload";
const Exam = lazy(() => import("./pages/student/Exam.jsx")
  .then((mod) => { try { sessionStorage.removeItem(RELOAD_FLAG); } catch { /* ignore */ } return mod; })
  .catch((err) => {
    let reloaded = false;
    try { reloaded = sessionStorage.getItem(RELOAD_FLAG) === "1"; sessionStorage.setItem(RELOAD_FLAG, "1"); } catch { /* ignore */ }
    if (!reloaded) { window.location.reload(); return new Promise(() => {}); }
    throw err;
  }));

function Root() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <ToastHost>
      <AuthProvider>
        <ConfirmHost>
          <Routes>
            <Route path="/" element={<Root />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/console/*"
              element={
                <RequireRole roles={["super_admin", "college_admin"]}>
                  <Console />
                </RequireRole>
              }
            />
            <Route
              path="/student"
              element={
                <RequireRole roles={["student"]}>
                  <StudentDashboard />
                </RequireRole>
              }
            />
            <Route
              path="/exam/:examId"
              element={
                <RequireRole roles={["student"]}>
                  <Suspense fallback={<div className="pre-start"><Loading /></div>}>
                    <Exam />
                  </Suspense>
                </RequireRole>
              }
            />
            <Route path="*" element={<Root />} />
          </Routes>
        </ConfirmHost>
      </AuthProvider>
    </ToastHost>
  );
}
