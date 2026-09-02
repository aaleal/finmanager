import * as React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, PiggyBank } from 'lucide-react';
import { api, ApiError, setCsrfToken } from '@/lib/api';
import type { SessionInfo } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Field, Input, PasswordInput } from '@/components/ui/input';

const schema = z
  .object({
    household_name: z.string().min(1, 'Dê um nome ao agregado'),
    display_name: z.string().min(1, 'Indique o seu nome'),
    email: z.string().min(1, 'Indique o seu email').email('Email inválido'),
    password: z.string().min(12, 'Use pelo menos 12 caracteres'),
    confirm: z.string().min(1, 'Repita a palavra-passe'),
  })
  .refine((values) => values.password === values.confirm, {
    path: ['confirm'],
    message: 'As palavras-passe não coincidem',
  });

type FormValues = z.infer<typeof schema>;

/**
 * First run of a clean installation.
 *
 * Reached only while the database has no users. There are no default credentials
 * to change afterwards: this form *is* how the first owner comes into existence,
 * and it signs them in on success (FR-7.9).
 */
export function SetupPage() {
  const queryClient = useQueryClient();
  const [error, setError] = React.useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      household_name: 'Casa',
      display_name: '',
      email: '',
      password: '',
      confirm: '',
    },
  });

  const setup = useMutation({
    mutationFn: ({ confirm: _confirm, ...payload }: FormValues) =>
      api.post<SessionInfo>('/setup', payload),
    onSuccess: (session) => {
      setCsrfToken(session.csrf_token);
      queryClient.setQueryData(['session'], session);
      queryClient.invalidateQueries();
    },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await setup.mutateAsync(values);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível concluir a configuração.');
    }
  }

  return (
    <div className="grid h-full lg:grid-cols-2">
      <div className="flex items-center justify-center overflow-y-auto px-6 py-12">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-2">
            <div className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <PiggyBank className="size-5" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">Configuração inicial</h1>
            <p className="text-sm text-muted-foreground">
              Esta instalação ainda não tem utilizadores. Crie o titular do agregado — é a única
              conta que nasce sem convite.
            </p>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <Field
              label="Nome do agregado"
              htmlFor="household_name"
              error={form.formState.errors.household_name?.message}
            >
              <Input id="household_name" autoFocus {...form.register('household_name')} />
            </Field>

            <Field
              label="O seu nome"
              htmlFor="display_name"
              error={form.formState.errors.display_name?.message}
            >
              <Input id="display_name" placeholder="Ana" {...form.register('display_name')} />
            </Field>

            <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="nome@exemplo.pt"
                {...form.register('email')}
              />
            </Field>

            <Field
              label="Palavra-passe"
              htmlFor="password"
              hint="Pelo menos 12 caracteres. Não há recuperação por email — guarde-a."
              error={form.formState.errors.password?.message}
            >
              <PasswordInput
                id="password"
                autoComplete="new-password"
                {...form.register('password')}
              />
            </Field>

            <Field
              label="Repetir palavra-passe"
              htmlFor="confirm"
              error={form.formState.errors.confirm?.message}
            >
              <PasswordInput
                id="confirm"
                autoComplete="new-password"
                {...form.register('confirm')}
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

            <Button type="submit" className="w-full" size="lg" loading={setup.isPending}>
              Criar agregado e entrar
            </Button>
          </form>

          <p className="text-xs text-muted-foreground">
            Os restantes membros são criados depois, em «Agregado» — incluindo dependentes sem
            acesso.
          </p>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-sidebar lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(59,130,246,0.28),transparent_55%),radial-gradient(circle_at_75%_75%,rgba(45,212,191,0.22),transparent_55%)]" />
        <div className="relative flex h-full flex-col justify-end gap-6 p-14 text-sidebar-foreground">
          <ul className="space-y-3 text-white/90">
            {[
              'Sem credenciais por omissão — nada para mudar depois.',
              'Os dados nunca saem do seu servidor.',
              'Os dados de demonstração são opcionais: ./fm seed.',
            ].map((line) => (
              <li key={line} className="flex items-start gap-2.5 text-sm">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
                {line}
              </li>
            ))}
          </ul>
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
