import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import { useSession } from '@/features/auth/session';
import { LoginPage } from '@/routes/login';
import { DashboardPage } from '@/routes/dashboard';
import { LegoPage } from '@/routes/lego';
import { ReviewPage } from '@/routes/review';
import { HouseholdPage } from '@/routes/household';
import { SettingsPage } from '@/routes/settings';
import { NotFoundPage } from '@/routes/not-found';
import { Skeleton } from '@/components/ui/feedback';

function BootScreen() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-64 space-y-3">
        <Skeleton className="h-8" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  );
}

export default function App() {
  const { session, isLoading } = useSession();

  if (isLoading) return <BootScreen />;
  if (!session) return <LoginPage />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/lego" element={<LegoPage />} />
        <Route path="/revisao" element={<ReviewPage />} />
        <Route path="/agregado" element={<HouseholdPage />} />
        <Route path="/definicoes" element={<SettingsPage />} />
        <Route path="/entrar" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
