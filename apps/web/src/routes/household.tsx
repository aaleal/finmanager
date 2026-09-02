import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  Baby,
  KeyRound,
  MoreHorizontal,
  Palette,
  Pencil,
  Plus,
  ShieldCheck,
  UserMinus,
  Users,
} from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import { cn } from '@/lib/utils';
import type { Entity, Member, Role } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, Input, PasswordInput } from '@/components/ui/input';
import {
  Checkbox,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { PageHeader, Skeleton } from '@/components/ui/feedback';
import { date } from '@/lib/format';

const ROLE_LABELS: Record<Role, string> = {
  OWNER: 'Titular',
  MEMBER: 'Membro',
  VIEWER: 'Leitor',
};

const memberSchema = z
  .object({
    display_name: z.string().min(1, 'Indique o nome'),
    is_dependent: z.boolean(),
    email: z.string().email('Email inválido').optional().or(z.literal('')),
    role: z.enum(['OWNER', 'MEMBER', 'VIEWER']),
    temporary_password: z.string().optional().or(z.literal('')),
    confirm_password: z.string().optional().or(z.literal('')),
  })
  .refine((values) => values.is_dependent || Boolean(values.email), {
    message: 'Indique um email',
    path: ['email'],
  })
  .refine((values) => values.is_dependent || (values.temporary_password ?? '').length >= 8, {
    message: 'Mínimo 8 caracteres',
    path: ['temporary_password'],
  })
  .refine(
    (values) => values.is_dependent || values.temporary_password === values.confirm_password,
    {
      message: 'As palavras-passe não coincidem',
      path: ['confirm_password'],
    },
  );

type MemberFormValues = z.infer<typeof memberSchema>;

function AddMemberDialog() {
  const [open, setOpen] = React.useState(false);
  const queryClient = useQueryClient();

  const form = useForm<MemberFormValues>({
    resolver: zodResolver(memberSchema),
    defaultValues: {
      display_name: '',
      is_dependent: false,
      email: '',
      role: 'MEMBER',
      temporary_password: '',
      confirm_password: '',
    },
  });
  const isDependent = form.watch('is_dependent');

  const create = useMutation({
    mutationFn: (values: MemberFormValues) =>
      api.post<Member>('/members', {
        display_name: values.display_name,
        is_dependent: values.is_dependent,
        email: values.is_dependent ? null : values.email,
        role: values.is_dependent ? 'VIEWER' : values.role,
        temporary_password: values.is_dependent ? null : values.temporary_password,
      }),
    onSuccess: () => {
      toast.success('Membro criado.');
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['entities'] });
      form.reset();
      setOpen(false);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar o membro.'),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Adicionar membro
        </Button>
      </DialogTrigger>
      <DialogContent size="sm">
        <form onSubmit={form.handleSubmit((values) => create.mutate(values))}>
          <DialogHeader>
            <DialogTitle>Adicionar membro</DialogTitle>
            <DialogDescription>
              Um dependente (por exemplo, uma criança) não tem email nem palavra-passe — existe
              apenas para lhe atribuir despesas.
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-border p-3">
              <Checkbox
                checked={isDependent}
                onCheckedChange={(checked) => form.setValue('is_dependent', checked === true)}
              />
              <span className="flex items-center gap-2 text-sm font-medium">
                <Baby className="size-4 text-muted-foreground" />É um dependente sem acesso
              </span>
            </label>

            <Field label="Nome" error={form.formState.errors.display_name?.message}>
              <Input placeholder="Clara" {...form.register('display_name')} />
            </Field>

            {!isDependent ? (
              <>
                <Field label="Email" error={form.formState.errors.email?.message}>
                  <Input type="email" placeholder="nome@exemplo.pt" {...form.register('email')} />
                </Field>

                <Field label="Função">
                  <Select
                    value={form.watch('role')}
                    onValueChange={(value) => form.setValue('role', value as Role)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="OWNER">Titular — controlo total</SelectItem>
                      <SelectItem value="MEMBER">Membro — lê e escreve tudo</SelectItem>
                      <SelectItem value="VIEWER">Leitor — apenas leitura</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>

                <Field
                  label="Palavra-passe temporária"
                  hint="O membro terá de a alterar no primeiro acesso."
                  error={form.formState.errors.temporary_password?.message}
                >
                  <PasswordInput
                    autoComplete="new-password"
                    {...form.register('temporary_password')}
                  />
                </Field>

                <Field
                  label="Repetir palavra-passe"
                  error={form.formState.errors.confirm_password?.message}
                >
                  <PasswordInput
                    autoComplete="new-password"
                    {...form.register('confirm_password')}
                  />
                </Field>
              </>
            ) : null}
          </DialogBody>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" loading={create.isPending}>
              Criar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The palette the API assigns from, offered as one click each, plus a free picker. */
const ENTITY_PALETTE = [
  '#2563eb',
  '#0d9488',
  '#c026d3',
  '#ea580c',
  '#65a30d',
  '#7c3aed',
  '#e11d48',
  '#0891b2',
];

function ColorPicker({ value, onChange }: { value: string; onChange: (color: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {ENTITY_PALETTE.map((color) => (
        <button
          key={color}
          type="button"
          aria-label={`Cor ${color}`}
          aria-pressed={value.toLowerCase() === color}
          onClick={() => onChange(color)}
          className={cn(
            'size-6 rounded-full border-2 transition-transform hover:scale-110',
            value.toLowerCase() === color ? 'border-foreground' : 'border-transparent',
          )}
          style={{ backgroundColor: color }}
        />
      ))}
      <label
        className="ml-1 flex size-6 cursor-pointer items-center justify-center rounded-full border border-dashed border-border"
        title="Escolher outra cor"
      >
        <Palette className="size-3.5 text-muted-foreground" />
        <input
          type="color"
          className="sr-only"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    </div>
  );
}

function EntityDialog({
  members,
  entity,
  open,
  onOpenChange,
}: {
  members: Member[];
  entity?: Entity;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = React.useState(entity?.name ?? '');
  const [color, setColor] = React.useState(entity?.color ?? ENTITY_PALETTE[0]);
  const [selected, setSelected] = React.useState<string[]>(entity?.member_ids ?? []);

  React.useEffect(() => {
    if (!open) return;
    setName(entity?.name ?? '');
    setColor(entity?.color ?? ENTITY_PALETTE[0]);
    setSelected(entity?.member_ids ?? []);
  }, [open, entity]);

  const save = useMutation({
    mutationFn: () => {
      const payload = { name, color, member_ids: selected };
      return entity
        ? api.patch<Entity>(`/entities/${entity.id}`, payload)
        : api.post<Entity>('/entities', payload);
    },
    onSuccess: () => {
      toast.success(entity ? 'Entidade atualizada.' : 'Entidade criada.');
      queryClient.invalidateQueries({ queryKey: ['entities'] });
      queryClient.invalidateQueries({ queryKey: ['session'] });
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível guardar.'),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{entity ? 'Editar entidade' : 'Nova entidade'}</DialogTitle>
          <DialogDescription>
            Uma entidade é um titular com um ou mais membros — por exemplo, o casal. A cor
            identifica-a em todos os módulos.
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <Field label="Nome">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ana & Bruno"
            />
          </Field>

          <Field label="Cor">
            <ColorPicker value={color} onChange={setColor} />
          </Field>

          <div className="space-y-2">
            <p className="text-sm font-medium">Membros</p>
            {members
              .filter((member) => member.is_active)
              .map((member) => (
                <label
                  key={member.user_id}
                  className="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <Checkbox
                    checked={selected.includes(member.user_id)}
                    onCheckedChange={(checked) =>
                      setSelected((previous) =>
                        checked === true
                          ? [...previous, member.user_id]
                          : previous.filter((id) => id !== member.user_id),
                      )
                    }
                  />
                  {member.display_name}
                </label>
              ))}
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={!name || selected.length === 0}
            loading={save.isPending}
          >
            {entity ? 'Guardar' : 'Criar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** An owner resetting someone else's password — the only recovery route, since there is no email. */
function ResetPasswordDialog({
  member,
  open,
  onOpenChange,
}: {
  member: Member | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = React.useState('');

  React.useEffect(() => {
    if (open) setPassword('');
  }, [open]);

  const reset = useMutation({
    mutationFn: () => api.patch(`/members/${member?.id}`, { new_password: password }),
    onSuccess: () => {
      toast.success('Palavra-passe definida. O membro terá de a alterar no próximo acesso.');
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível alterar.'),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Definir palavra-passe</DialogTitle>
          <DialogDescription>
            {member?.display_name} vai receber esta palavra-passe temporária e terá de a alterar no
            próximo acesso. As sessões abertas dessa pessoa são terminadas.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <Field label="Palavra-passe temporária" hint="Mínimo 8 caracteres.">
            <Input
              type="text"
              autoComplete="off"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => reset.mutate()}
            disabled={password.length < 8}
            loading={reset.isPending}
          >
            Definir
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function HouseholdPage() {
  const { isOwner, session } = useSession();
  const queryClient = useQueryClient();
  const [entityDialog, setEntityDialog] = React.useState<{ open: boolean; entity?: Entity }>({
    open: false,
  });
  const [passwordFor, setPasswordFor] = React.useState<Member | null>(null);

  const members = useQuery({ queryKey: ['members'], queryFn: () => api.get<Member[]>('/members') });
  const entities = useQuery({
    queryKey: ['entities'],
    queryFn: () => api.get<Entity[]>('/entities'),
  });

  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) => api.patch(`/members/${id}`, { role }),
    onSuccess: () => {
      toast.success('Função atualizada.');
      queryClient.invalidateQueries({ queryKey: ['members'] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Erro.'),
  });

  const removeMember = useMutation({
    mutationFn: (id: string) => api.delete(`/members/${id}`),
    onSuccess: () => {
      toast.success('Membro removido.');
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['entities'] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Erro.'),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agregado"
        description={`${session?.household_name} · toda a gente lê tudo; a função define apenas o que se pode alterar.`}
      />

      <Tabs defaultValue="members">
        <TabsList>
          <TabsTrigger value="members">
            <Users className="size-4" />
            Membros
          </TabsTrigger>
          <TabsTrigger value="entities">
            <ShieldCheck className="size-4" />
            Entidades
          </TabsTrigger>
        </TabsList>

        <TabsContent value="members" className="space-y-4">
          {isOwner ? (
            <div className="flex justify-end">
              <AddMemberDialog />
            </div>
          ) : null}

          <Card>
            <CardContent className="p-0">
              {members.isLoading ? (
                <div className="space-y-2 p-5">
                  <Skeleton className="h-10" />
                  <Skeleton className="h-10" />
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nome</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Função</TableHead>
                      <TableHead>Desde</TableHead>
                      <TableHead>Estado</TableHead>
                      {isOwner ? <TableHead className="w-10" /> : null}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.data?.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell className="font-medium">
                          <span className="flex items-center gap-2">
                            {member.display_name}
                            {member.is_dependent ? (
                              <Badge variant="muted">
                                <Baby />
                                dependente
                              </Badge>
                            ) : null}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {member.email ?? '—'}
                        </TableCell>
                        <TableCell>
                          <Badge variant={member.role === 'OWNER' ? 'default' : 'secondary'}>
                            {ROLE_LABELS[member.role]}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {date(member.joined_at)}
                        </TableCell>
                        <TableCell>
                          {member.is_active ? (
                            <Badge variant="success">ativo</Badge>
                          ) : (
                            <Badge variant="muted">saiu</Badge>
                          )}
                        </TableCell>
                        {isOwner ? (
                          <TableCell>
                            {member.is_active && !member.is_dependent ? (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon-sm">
                                    <MoreHorizontal />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onSelect={() => setPasswordFor(member)}>
                                    <KeyRound />
                                    Definir palavra-passe
                                  </DropdownMenuItem>
                                  {(['OWNER', 'MEMBER', 'VIEWER'] as Role[])
                                    .filter((role) => role !== member.role)
                                    .map((role) => (
                                      <DropdownMenuItem
                                        key={role}
                                        onSelect={() => changeRole.mutate({ id: member.id, role })}
                                      >
                                        Tornar {ROLE_LABELS[role].toLowerCase()}
                                      </DropdownMenuItem>
                                    ))}
                                  <DropdownMenuItem
                                    destructive
                                    onSelect={() => removeMember.mutate(member.id)}
                                  >
                                    <UserMinus />
                                    Remover do agregado
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            ) : null}
                          </TableCell>
                        ) : null}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="entities" className="space-y-4">
          {isOwner ? (
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setEntityDialog({ open: true })}>
                <Plus />
                Nova entidade
              </Button>
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {entities.data?.map((entity) => {
              const entityMembers = (members.data ?? []).filter((member) =>
                entity.member_ids.includes(member.user_id),
              );
              return (
                <Card key={entity.id}>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2">
                      <span
                        className="size-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: entity.color ?? '#94a3b8' }}
                      />
                      <span className="truncate">{entity.name}</span>
                      {isOwner ? (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="ml-auto"
                          title="Editar entidade"
                          onClick={() => setEntityDialog({ open: true, entity })}
                        >
                          <Pencil />
                        </Button>
                      ) : null}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      {entityMembers.map((member) => member.display_name).join(', ') || '—'}
                    </p>
                    <Separator />
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {entity.member_ids.length === 1 ? 'individual' : 'conjunta'}
                      </Badge>
                      {entity.is_readonly ? <Badge variant="warning">só leitura</Badge> : null}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>

      <EntityDialog
        members={members.data ?? []}
        entity={entityDialog.entity}
        open={entityDialog.open}
        onOpenChange={(open) => setEntityDialog((previous) => ({ ...previous, open }))}
      />
      <ResetPasswordDialog
        member={passwordFor}
        open={Boolean(passwordFor)}
        onOpenChange={(open) => {
          if (!open) setPasswordFor(null);
        }}
      />
    </div>
  );
}
