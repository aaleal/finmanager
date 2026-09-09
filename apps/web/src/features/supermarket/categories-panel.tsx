import * as React from 'react';
import { Check, ChevronRight, GitMerge, Move, PencilLine, Plus, Trash2, X } from 'lucide-react';
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
import { Checkbox } from '@/components/ui/primitives';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { cn } from '@/lib/utils';
import { useSession } from '@/features/auth/session';
import { CategoryPicker } from './category-picker';
import {
  useCategoryImpact,
  useCategoryTree,
  useCreateCategory,
  useMergeCategories,
  useRenameCategory,
  useReparentCategory,
  useRetireCategory,
} from './catalogue-api';

interface TreeNode extends CategoryTreeNode {
  children: TreeNode[];
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
  const [expanded, setExpanded] = React.useState(true);
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
            onClick={() => setExpanded((previous) => !previous)}
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

export function CategoriesPanel() {
  const { canWrite } = useSession();
  const categories = useCategoryTree();
  const [createOpen, setCreateOpen] = React.useState(false);

  const tree = React.useMemo(() => buildTree(categories.data ?? []), [categories.data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Mudar o nome não custa nada — as linhas referem-se às categorias por identificador. Mover
          recalcula os ascendentes dos produtos afetados numa só transação auditada.
        </p>
        {canWrite ? (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus />
            Nova categoria
          </Button>
        ) : null}
      </div>

      {categories.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-8 rounded-lg" />
          ))}
        </div>
      ) : !tree.length ? (
        <EmptyState title="Sem categorias na taxonomia GROCERY." />
      ) : (
        <ul className="space-y-0.5 rounded-xl border border-border bg-card p-3">
          {tree.map((node) => (
            <CategoryNodeRow key={node.id} node={node} depth={0} />
          ))}
        </ul>
      )}

      <NewCategoryDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
