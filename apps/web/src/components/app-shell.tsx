import * as React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Car,
  CreditCard,
  Gauge,
  HeartPulse,
  Inbox,
  LogOut,
  Menu,
  Moon,
  PiggyBank,
  Settings,
  ShoppingCart,
  Sun,
  Users,
  Zap,
  ToyBrick,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from '@/features/auth/session';
import { EntitySelector } from '@/components/entity-selector';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Dialog, SheetContent } from '@/components/ui/dialog';
import { api } from '@/lib/api';
import type { ReviewSummary } from '@/lib/types';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme';

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  planned?: boolean;
}

const PRIMARY_NAV: NavItem[] = [
  { to: '/', label: 'Painel', icon: Gauge },
  { to: '/supermercado', label: 'Supermercado', icon: ShoppingCart },
  { to: '/lego', label: 'Coleção LEGO', icon: ToyBrick },
  { to: '/revisao', label: 'Fila de revisão', icon: Inbox },
];

const PLANNED_NAV: NavItem[] = [
  { to: '/banca', label: 'Banca', icon: CreditCard, planned: true },
  { to: '/saude', label: 'Saúde', icon: HeartPulse, planned: true },
  { to: '/utilidades', label: 'Utilidades', icon: Zap, planned: true },
  { to: '/veiculos', label: 'Veículos', icon: Car, planned: true },
  { to: '/patrimonio', label: 'Património', icon: PiggyBank, planned: true },
];

const ADMIN_NAV: NavItem[] = [
  { to: '/agregado', label: 'Agregado', icon: Users },
  { to: '/definicoes', label: 'Definições', icon: Settings },
];

const SIDEBAR_COLLAPSED_KEY = 'finmanager.sidebar.collapsed';

function NavSection({
  title,
  items,
  reviewCount,
  onNavigate,
  collapsed,
}: {
  title?: string;
  items: NavItem[];
  reviewCount?: number;
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  return (
    <div className="space-y-1">
      {title && !collapsed ? (
        <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/45">
          {title}
        </p>
      ) : null}
      {items.map((item) => {
        const Icon = item.icon;
        if (item.planned) {
          return (
            <div
              key={item.to}
              className={cn(
                'flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/35',
                collapsed && 'justify-center px-2',
              )}
              title={
                collapsed
                  ? `${item.label} — disponível numa fase seguinte`
                  : 'Disponível numa fase seguinte'
              }
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed ? (
                <>
                  <span className="flex-1 truncate">{item.label}</span>
                  <span className="text-[10px] uppercase tracking-wide">em breve</span>
                </>
              ) : null}
            </div>
          );
        }
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                collapsed && 'justify-center px-2',
                isActive
                  ? 'bg-sidebar-accent text-white'
                  : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white',
              )
            }
          >
            <Icon className="size-4 shrink-0" />
            {!collapsed ? <span className="flex-1 truncate">{item.label}</span> : null}
            {!collapsed && item.to === '/revisao' && reviewCount ? (
              <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                {reviewCount}
              </span>
            ) : null}
          </NavLink>
        );
      })}
    </div>
  );
}

function SidebarContent({
  reviewCount,
  onNavigate,
  collapsed = false,
  collapsible = false,
  onToggleCollapsed,
}: {
  reviewCount: number;
  onNavigate?: () => void;
  collapsed?: boolean;
  collapsible?: boolean;
  onToggleCollapsed?: () => void;
}) {
  const { session } = useSession();
  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div
        className={cn(
          'flex h-16 shrink-0 items-center gap-2.5 border-b border-sidebar-border px-5',
          collapsed && 'justify-center px-0',
        )}
      >
        {collapsible ? (
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Expandir menu' : 'Colapsar menu'}
            title={collapsed ? 'Expandir menu' : 'Colapsar menu'}
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/85"
          >
            <PiggyBank className="size-4" />
          </button>
        ) : (
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <PiggyBank className="size-4" />
          </div>
        )}
        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">FinManager</p>
            <p className="truncate text-[11px] text-sidebar-foreground/55">
              {session?.household_name ?? 'Agregado'}
            </p>
          </div>
        ) : null}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        <NavSection
          items={PRIMARY_NAV}
          reviewCount={reviewCount}
          onNavigate={onNavigate}
          collapsed={collapsed}
        />
        <NavSection
          title="Próximas fases"
          items={PLANNED_NAV}
          onNavigate={onNavigate}
          collapsed={collapsed}
        />
        <NavSection
          title="Administração"
          items={ADMIN_NAV}
          onNavigate={onNavigate}
          collapsed={collapsed}
        />
      </nav>

      {!collapsed ? (
        <div className="border-t border-sidebar-border p-3 text-[11px] text-sidebar-foreground/45">
          <p>Fase 1 · Fundação + LEGO</p>
        </div>
      ) : null}
    </div>
  );
}

function UserMenu() {
  const { session, logout } = useSession();
  const { theme, toggle } = useTheme();
  const initials = (session?.user.display_name ?? '?')
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {initials}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="normal-case">
          <p className="text-sm font-medium text-foreground">{session?.user.display_name}</p>
          <p className="truncate text-xs font-normal text-muted-foreground">
            {session?.user.email}
          </p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={toggle}>
          {theme === 'dark' ? <Sun /> : <Moon />}
          {theme === 'dark' ? 'Tema claro' : 'Tema escuro'}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem destructive onSelect={() => void logout()}>
          <LogOut />
          Terminar sessão
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(
    () => window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1',
  );
  const location = useLocation();
  const { session } = useSession();

  const reviewQuery = useQuery({
    queryKey: ['review', 'summary', session?.active_entity_id ?? 'all'],
    queryFn: () => api.get<ReviewSummary>('/review/summary'),
    enabled: Boolean(session),
    staleTime: 30_000,
  });

  React.useEffect(() => setMobileOpen(false), [location.pathname]);
  React.useEffect(() => {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  return (
    <div className="flex h-full">
      <aside
        className={cn(
          'hidden shrink-0 transition-[width] duration-200 lg:block',
          collapsed ? 'w-[4.5rem]' : 'w-64',
        )}
      >
        <SidebarContent
          reviewCount={reviewQuery.data?.pending ?? 0}
          collapsed={collapsed}
          collapsible
          onToggleCollapsed={() => setCollapsed((value) => !value)}
        />
      </aside>

      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 sm:max-w-[17rem]">
          <SidebarContent
            reviewCount={reviewQuery.data?.pending ?? 0}
            onNavigate={() => setMobileOpen(false)}
          />
        </SheetContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Abrir menu"
          >
            <Menu />
          </Button>

          <div className="flex-1" />

          {session?.role === 'VIEWER' ? (
            <Badge variant="warning" className="hidden sm:inline-flex">
              Apenas leitura
            </Badge>
          ) : null}
          <EntitySelector />
          <UserMenu />
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1500px] animate-fade-in px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
