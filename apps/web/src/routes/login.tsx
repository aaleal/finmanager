import * as React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { PiggyBank } from 'lucide-react';
import { useSession } from '@/features/auth/session';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';
import { ApiError } from '@/lib/api';

const schema = z.object({
  email: z.string().min(1, 'Indique o seu email').email('Email inválido'),
  password: z.string().min(1, 'Indique a palavra-passe'),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useSession();
  const [error, setError] = React.useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await login(values.email, values.password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível iniciar sessão.');
    }
  }

  return (
    <div className="grid h-full lg:grid-cols-2">
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-2">
            <div className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <PiggyBank className="size-5" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">Bem-vindo de volta</h1>
            <p className="text-sm text-muted-foreground">
              Inicie sessão para aceder às finanças do agregado.
            </p>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                autoFocus
                placeholder="nome@exemplo.pt"
                {...form.register('email')}
              />
            </Field>

            <Field
              label="Palavra-passe"
              htmlFor="password"
              error={form.formState.errors.password?.message}
            >
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                {...form.register('password')}
              />
            </Field>

            {error ? (
              <div
                role="alert"
                className="rounded-lg border border-destructive/30 bg-destructive/8 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </div>
            ) : null}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={form.formState.isSubmitting}
            >
              Entrar
            </Button>
          </form>

          <p className="text-xs text-muted-foreground">
            Servidor privado do agregado. Todos os dados ficam no seu NAS.
          </p>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-sidebar lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(59,130,246,0.28),transparent_55%),radial-gradient(circle_at_75%_75%,rgba(45,212,191,0.22),transparent_55%)]" />
        <div className="relative flex h-full flex-col justify-end gap-6 p-14 text-sidebar-foreground">
          <blockquote className="max-w-md text-2xl font-medium leading-snug text-white">
            Um único sítio para o supermercado, o banco, a saúde, a casa, os carros — e a coleção
            de LEGO.
          </blockquote>
          <div className="space-y-1 text-sm">
            <p className="font-medium text-white/90">FinManager</p>
            <p className="text-sidebar-foreground/60">
              Privado por desenho · pt-PT · EUR · Europe/Lisbon
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
