import "./globals.css";
import Navbar from "@/components/Navbar";
import AnalysisAssistantDrawer from "@/components/AnalysisAssistantDrawer";

export const metadata = {
  title: "SchemaSense - Natural Language Database Explorer",
  description: "Connect Postgres or MySQL, ask questions in plain English, get safe SQL, charts, and insights.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 flex flex-col font-sans antialiased text-slate-900">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
        <AnalysisAssistantDrawer />
      </body>
    </html>
  );
}

