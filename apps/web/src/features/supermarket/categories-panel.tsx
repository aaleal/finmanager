import * as React from 'react';
import {
  Check,
  ChevronRight,
  Download,
  FoldVertical,
  GitMerge,
  Move,
  PencilLine,
  Plus,
  Trash2,
  UnfoldVertical,
  Upload,
  X,
} from 'lucide-react';
import type { CategoryResult, CategoryTreeNode } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/primitives';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { num } from '@/lib/format';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import { CategoryImportDialog } from './category-import-dialog';
import { CategoryPicker } from './category-picker';
import {
  useCategoryImpact,
  useCategoryTree,
  useCreateCategory,
  useDeleteAllCategories,
  useExportCategories,
  useLoadDefaultCategories,
  useMergeCategories,
  usePurgeCategories,
  useRenameCategory,
  useReparentCategory,
  useRetireCategory,
} from './catalogue-api';

interface TreeNode extends CategoryTreeNode {
  children: TreeNode[];
}

/** Lifted so the toolbar's "collapse/expand all" can reach every row without prop
 *  drilling through the recursive tree — a node with no entry here is expanded. */
const ExpansionContext = React.createContext<{
  isCollapsed: (id: string) => boolean;
  toggle: (id: string) => void;
} | null>(null);

function useExpansion() {
  const value = React.useContext(ExpansionContext);
  if (!value) throw new Error('useExpansion must be used within CategoriesPanel');
  return value;
}

/** Counted from the already-fetched tree — one query, no extra round trip for a summary bar. */
function CategoryStatsRow({ nodes, isLoading }: { nodes: CategoryTreeNode[]; isLoading: boolean }) {
  const counts = React.useMemo(() => {
    const byLevel = { 1: 0, 2: 0, 3: 0 };
    let productsCatalogued = 0;
    for (const node of nodes) {
      byLevel[node.level as 1 | 2 | 3] = (byLevel[node.level as 1 | 2 | 3] ?? 0) + 1;
      productsCatalogued += node.product_count;
    }
    return { byLevel, productsCatalogued };
  }, [nodes]);

  if (isLoading) return <Skeleton className="h-10 rounded-xl" />;

  const items = [
    { label: 'categorias', value: num(nodes.length) },
    { label: 'nível 1', value: num(counts.byLevel[1]) },
    { label: 'nível 2', value: num(counts.byLevel[2]) },
    { label: 'nível 3', value: num(counts.byLevel[3]) },
    { label: '', value: ' | ' },
    { label: 'produtos catalogados', value: num(counts.productsCatalogued) },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-border bg-card px-4 py-2.5 text-sm">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="flex items-baseline gap-1.5">
          <span className="numeric font-semibold">{item.value}</span>
          <span className="text-xs text-muted-foreground">{item.label}</span>
        </span>
      ))}
    </div>
  );
}

/** Built from `parent_id`, not by slicing the display path: a category is free to
 *  contain the path separator in its own name. */
function buildTree(nodes: CategoryTreeNode[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  for (const node of nodes) byId.set(node.id, { ...node, children: [] });

  const roots: TreeNode[] = [];
  for (const node of nodes) {
    const tree = byId.get(node.id);
    if (!tree) continue;
    const parent = node.parent_id ? byId.get(node.parent_id) : undefined;
    if (parent) parent.children.push(tree);
    else roots.push(tree);
  }

  function sortRecursive(list: TreeNode[]) {
    list.sort((a, b) => a.display_name_pt.localeCompare(b.display_name_pt, 'pt-PT'));
    for (const node of list) sortRecursive(node.children);
  }
  sortRecursive(roots);
  return roots;
}

function ImpactNote({ nodeId }: { nodeId: string }) {
  const impact = useCategoryImpact(nodeId);
  if (impact.isLoading || !impact.data) return <Skeleton className="h-4 w-48" />;
  return (
    <p className="text-sm font-medium">
      Vai afetar {impact.data.master_products} produto(s) e {impact.data.receipt_items} linha(s).
    </p>
  );
}

function MoveDialog({
  node,
  open,
  onOpenChange,
}: {
  node: TreeNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const reparent = useReparentCategory();
  const [parent, setParent] = React.useState<CategoryResult | null>(null);
  const [topLevel, setTopLevel] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setParent(null);
      setTopLevel(false);
    }
  }, [open]);

  const canConfirm = topLevel || Boolean(parent);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Mover categoria</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {open ? <ImpactNote nodeId={node.id} /> : null}
          <Field label="Novo pai">
            <CategoryPicker
              value={topLevel ? 'Categoria de topo' : (parent?.path ?? null)}
              disabled={topLevel}
              onSelect={(category) => {
                setParent(category);
                setTopLevel(false);
              }}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={topLevel}
              onCheckedChange={(checked) => {
                const value = checked === true;
                setTopLevel(value);
                if (value) setParent(null);
              }}
            />
            Tornar categoria de topo
          </label>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!canConfirm}
            loading={reparent.isPending}
            onClick={async () => {
              await reparent.mutateAsync({
                categoryId: node.id,
                parentId: topLevel ? null : (parent?.id ?? null),
              });
              onOpenChange(false);
            }}
          >
            Mover
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MergeDialog({
  node,
  open,
  onOpenChange,
}: {
  node: TreeNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const merge = useMergeCategories();
  const [target, setTarget] = React.useState<CategoryResult | null>(null);

  React.useEffect(() => {
    if (open) setTarget(null);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Fundir categoria</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {open ? <ImpactNote nodeId={node.id} /> : null}
          <Field label="Fundir em">
            <CategoryPicker value={target?.path ?? null} onSelect={setTarget} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!target}
            loading={merge.isPending}
            onClick={async () => {
              if (!target) return;
              await merge.mutateAsync({ categoryId: node.id, targetId: target.id });
              onOpenChange(false);
            }}
          >
            Fundir
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RetireDialog({
  node,
  open,
  onOpenChange,
}: {
  node: TreeNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const retire = useRetireCategory();
  const impact = useCategoryImpact(open ? node.id : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Retirar categoria</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3">
          {open ? <ImpactNote nodeId={node.id} /> : null}
          {open && node.level < 3 && impact.data && impact.data.descendants > 0 ? (
            <p className="text-sm font-medium text-destructive">
              Vai eliminar também {impact.data.descendants} sub-categoria(s) desta árvore.
            </p>
          ) : null}
          <p className="text-sm text-muted-foreground">
            A categoria fica marcada como retirada e deixa de aparecer nas listas de escolha.
          </p>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={impact.data?.in_use}
            loading={retire.isPending}
            onClick={async () => {
              await retire.mutateAsync(node.id);
              onOpenChange(false);
            }}
          >
            Retirar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CategoryNodeRow({ node, depth }: { node: TreeNode; depth: number }) {
  const { canWrite } = useSession();
  const rename = useRenameCategory();
  const impact = useCategoryImpact(node.id);
  const { isCollapsed, toggle } = useExpansion();
  const expanded = !isCollapsed(node.id);
  const [renaming, setRenaming] = React.useState(false);
  const [nameDraft, setNameDraft] = React.useState(node.display_name_pt);
  const [moveOpen, setMoveOpen] = React.useState(false);
  const [mergeOpen, setMergeOpen] = React.useState(false);
  const [retireOpen, setRetireOpen] = React.useState(false);

  function commitRename() {
    const trimmed = nameDraft.trim();
    setRenaming(false);
    if (!trimmed || trimmed === node.display_name_pt) return;
    rename.mutate({ categoryId: node.id, name: trimmed });
  }

  return (
    <li>
      <div className="flex flex-wrap items-center gap-2 rounded-md px-1 py-1.5 hover:bg-muted/50">
        {node.children.length ? (
          <button
            type="button"
            onClick={() => toggle(node.id)}
            aria-label={
              expanded ? `Fechar ${node.display_name_pt}` : `Abrir ${node.display_name_pt}`
            }
            aria-expanded={expanded}
            className="rounded p-1 text-muted-foreground hover:bg-muted"
          >
            <ChevronRight className={cn('size-4 transition-transform', expanded && 'rotate-90')} />
          </button>
        ) : (
          <span className="size-6 shrink-0" aria-hidden />
        )}
        <Badge variant="outline" className="shrink-0">
          N{node.level}
        </Badge>

        {renaming ? (
          <>
            <Input
              autoFocus
              className="h-7 w-52"
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') commitRename();
                if (event.key === 'Escape') {
                  setRenaming(false);
                  setNameDraft(node.display_name_pt);
                }
              }}
            />
            <Button size="icon-sm" variant="ghost" onClick={commitRename} aria-label="Guardar nome">
              <Check />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="Cancelar"
              onClick={() => {
                setRenaming(false);
                setNameDraft(node.display_name_pt);
              }}
            >
              <X />
            </Button>
          </>
        ) : (
          <span className="flex-1 truncate text-sm font-medium">{node.display_name_pt}</span>
        )}

        {canWrite && !renaming ? (
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => setRenaming(true)}>
              <PencilLine />
              Renomear
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMoveOpen(true)}>
              <Move />
              Mover
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMergeOpen(true)}>
              <GitMerge />
              Fundir noutra
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={impact.data?.in_use}
              title={
                impact.data?.in_use
                  ? 'Esta categoria está em uso. Funda-a noutra em vez de a retirar.'
                  : undefined
              }
              onClick={() => setRetireOpen(true)}
            >
              <Trash2 />
              Retirar
            </Button>
          </div>
        ) : null}
      </div>

      {node.children.length && expanded ? (
        <ul className={cn('space-y-0.5', depth < 2 && 'ml-6 border-l border-border pl-2')}>
          {node.children.map((child) => (
            <CategoryNodeRow key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}

      <MoveDialog node={node} open={moveOpen} onOpenChange={setMoveOpen} />
      <MergeDialog node={node} open={mergeOpen} onOpenChange={setMergeOpen} />
      <RetireDialog node={node} open={retireOpen} onOpenChange={setRetireOpen} />
    </li>
  );
}

function NewCategoryDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateCategory();
  const [name, setName] = React.useState('');
  const [parent, setParent] = React.useState<CategoryResult | null>(null);
  const [topLevel, setTopLevel] = React.useState(true);

  React.useEffect(() => {
    if (open) {
      setName('');
      setParent(null);
      setTopLevel(true);
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Nova categoria</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <Field label="Nome">
            <Input autoFocus value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="Categoria-mãe">
            <CategoryPicker
              value={topLevel ? 'Categoria de topo' : (parent?.path ?? null)}
              disabled={topLevel}
              onSelect={(category) => {
                setParent(category);
                setTopLevel(false);
              }}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={topLevel}
              onCheckedChange={(checked) => {
                const value = checked === true;
                setTopLevel(value);
                if (value) setParent(null);
              }}
            />
            Tornar categoria de topo
          </label>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!name.trim() || (!topLevel && !parent)}
            loading={create.isPending}
            onClick={async () => {
              await create.mutateAsync({
                display_name_pt: name.trim(),
                parent_id: topLevel ? null : (parent?.id ?? null),
              });
              onOpenChange(false);
            }}
          >
            Criar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteAllDialog({
  nodes,
  rootIds,
  open,
  onOpenChange,
}: {
  nodes: CategoryTreeNode[];
  rootIds: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const deleteAll = useDeleteAllCategories();
  const [hardDelete, setHardDelete] = React.useState(false);
  const [purgeOpen, setPurgeOpen] = React.useState(false);

  React.useEffect(() => {
    if (!open) setHardDelete(false);
  }, [open]);

  const l1 = nodes.filter((node) => node.level === 1).length;
  const l2 = nodes.filter((node) => node.level === 2).length;
  const l3 = nodes.filter((node) => node.level === 3).length;
  const productCount = nodes.reduce((sum, node) => sum + node.product_count, 0);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              Eliminar todas as categorias
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4 text-sm">
            {/* Bloco de Categorias Afetadas */}
            <div className="space-y-2">
              <p className="font-medium text-destructive">
                Isto afeta o seguinte volume de categorias:
              </p>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-md border bg-muted/40 p-2">
                  <span className="block text-xs text-muted-foreground">Nível 1</span>
                  <span className="text-base font-semibold">{num(l1)}</span>
                </div>
                <div className="rounded-md border bg-muted/40 p-2">
                  <span className="block text-xs text-muted-foreground">Nível 2</span>
                  <span className="text-base font-semibold">{num(l2)}</span>
                </div>
                <div className="rounded-md border bg-muted/40 p-2">
                  <span className="block text-xs text-muted-foreground">Nível 3</span>
                  <span className="text-base font-semibold">{num(l3)}</span>
                </div>
              </div>
              <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
                <span>Total de categorias</span>
                <span className="text-sm font-semibold text-foreground">{num(nodes.length)}</span>
              </div>
            </div>

            {/* Impacto em Produtos */}
            <div
              className={`rounded-md p-2.5 text-xs font-medium ${
                productCount > 0
                  ? 'border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300'
                  : 'bg-muted/50 text-muted-foreground'
              }`}
            >
              {productCount > 0
                ? `⚠️ ${num(productCount)} produto(s) têm alguma destas categorias atribuída.`
                : '✓ Nenhum produto tem alguma destas categorias atribuída.'}
            </div>

            <p className="text-sm text-muted-foreground">
              Por norma, uma categoria (ou sub-árvore) ainda em uso por algum produto é apenas
              retirada — ignorada, não eliminada à força — e pode voltar aqui depois de a fundir
              noutra.
            </p>

            <label className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
              <Checkbox
                checked={hardDelete}
                onCheckedChange={(checked) => setHardDelete(checked === true)}
              />
              <span>
                Eliminar <strong>definitivamente</strong>, incluindo as categorias em uso — os
                produtos afetados ficam sem categoria em vez de bloquear a eliminação.
              </span>
            </label>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            {hardDelete ? (
              <Button
                variant="destructive"
                onClick={() => {
                  onOpenChange(false);
                  setPurgeOpen(true);
                }}
              >
                Continuar
              </Button>
            ) : (
              <Button
                variant="destructive"
                loading={deleteAll.isPending}
                onClick={async () => {
                  await deleteAll.mutateAsync(rootIds);
                  onOpenChange(false);
                }}
              >
                Eliminar tudo
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <PurgeCategoriesDialog open={purgeOpen} onOpenChange={setPurgeOpen} />
    </>
  );
}

function PurgeCategoriesDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const purge = usePurgeCategories();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trash2 className="size-4" />
            Confirmar eliminação definitiva
          </DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3 text-sm text-muted-foreground">
          <p>
            Isto elimina <strong className="text-foreground">definitivamente</strong> toda a árvore
            de categorias, mesmo as que ainda estão em uso — os produtos afetados ficam sem
            categoria, nunca eliminados. Não pode ser desfeito.
          </p>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            loading={purge.isPending}
            onClick={async () => {
              await purge.mutateAsync();
              onOpenChange(false);
            }}
          >
            Eliminar definitivamente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CategoriesPanel() {
  const { canWrite } = useSession();
  const categories = useCategoryTree();
  const exportCategories = useExportCategories();
  const loadDefaults = useLoadDefaultCategories();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [importOpen, setImportOpen] = React.useState(false);
  const [deleteAllOpen, setDeleteAllOpen] = React.useState(false);
  const [collapsedIds, setCollapsedIds] = React.useState<Set<string>>(new Set());

  const nodes = React.useMemo(() => categories.data ?? [], [categories.data]);
  const tree = React.useMemo(() => buildTree(nodes), [nodes]);

  const expansion = React.useMemo(
    () => ({
      isCollapsed: (id: string) => collapsedIds.has(id),
      toggle: (id: string) =>
        setCollapsedIds((previous) => {
          const next = new Set(previous);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        }),
    }),
    [collapsedIds],
  );

  /** `levels` picks which rows the bulk action touches — a leaf (N3) has no
   *  children, so including it is harmless but never does anything visible. */
  function setCollapsedForLevels(levels: (1 | 2)[], collapsed: boolean) {
    const ids = nodes.filter((node) => levels.includes(node.level as 1 | 2)).map((node) => node.id);
    setCollapsedIds((previous) => {
      const next = new Set(previous);
      for (const id of ids) {
        if (collapsed) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }

  const rootIds = tree.map((node) => node.id);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Mudar o nome não custa nada — as linhas referem-se às categorias por identificador. Mover
          recalcula os ascendentes dos produtos afetados numa só transação auditada.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            loading={exportCategories.isPending}
            onClick={() => exportCategories.mutate()}
          >
            <Download />
            Exportar
          </Button>
          {canWrite ? (
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload />
              Importar
            </Button>
          ) : null}
          {canWrite ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus />
              Nova categoria
            </Button>
          ) : null}
        </div>
      </div>

      <CategoryStatsRow nodes={nodes} isLoading={categories.isLoading} />

      {categories.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-8 rounded-lg" />
          ))}
        </div>
      ) : !tree.length ? (
        <EmptyState
          title="Sem categorias na taxonomia GROCERY."
          description={
            canWrite
              ? 'Pretende fazer loading das categorias por defeito?'
              : 'Peça a um utilizador com permissão de escrita para carregar as categorias por defeito.'
          }
          action={
            canWrite ? (
              <Button loading={loadDefaults.isPending} onClick={() => loadDefaults.mutate()}>
                <Download />
                Carregar categorias por defeito
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <FoldVertical />
                  Colapsar
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([1], true)}>
                  Nível 1
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([2], true)}>
                  Nível 2
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([1, 2], true)}>
                  Níveis 1 e 2
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <UnfoldVertical />
                  Expandir
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([1], false)}>
                  Nível 1
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([2], false)}>
                  Nível 2
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setCollapsedForLevels([1, 2], false)}>
                  Níveis 1 e 2
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            {canWrite ? (
              <Button
                variant="destructive"
                size="sm"
                className="ml-auto"
                onClick={() => setDeleteAllOpen(true)}
              >
                <Trash2 />
                Eliminar tudo
              </Button>
            ) : null}
          </div>

          <ExpansionContext.Provider value={expansion}>
            <ul className="space-y-0.5 rounded-xl border border-border bg-card p-3">
              {tree.map((node) => (
                <CategoryNodeRow key={node.id} node={node} depth={0} />
              ))}
            </ul>
          </ExpansionContext.Provider>
        </>
      )}

      <NewCategoryDialog open={createOpen} onOpenChange={setCreateOpen} />
      <CategoryImportDialog open={importOpen} onOpenChange={setImportOpen} />
      <DeleteAllDialog
        nodes={nodes}
        rootIds={rootIds}
        open={deleteAllOpen}
        onOpenChange={setDeleteAllOpen}
      />
    </div>
  );
}
