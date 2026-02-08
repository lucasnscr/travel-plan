import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { Footer } from "./Footer";
import { ChatDrawer } from "@/components/Chat/ChatDrawer";

export function AppShell() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface-950">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 xl:p-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
      <Footer />
      <ChatDrawer />
    </div>
  );
}
