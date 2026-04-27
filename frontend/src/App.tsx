import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  BanknoteArrowDown,
  CheckCircle,
  CircleDollarSign,
  Clock3,
  Landmark,
  Loader2,
  RefreshCw,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Merchant {
  id?: number;
  username?: string;
  email?: string;
  available_balance_paise: number;
  held_balance_paise: number;
  total_balance_paise: number;
}

interface Transaction {
  id: string;
  amount_paise: number;
  description?: string;
  status?: string;
  created_at: string;
  bank_account_id?: string;
}

interface PayoutResponse {
  id: string;
  amount_paise: number;
  bank_account_id: string;
  status: string;
  created_at: string;
}

function formatPaise(paise = 0): string {
  return `₹${(paise / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatStatus(status: string): React.ReactNode {
  const variants: Record<
    string,
    "default" | "secondary" | "destructive" | "outline"
  > = {
    pending: "secondary",
    processing: "outline",
    completed: "default",
    failed: "destructive",
  };

  return (
    <Badge className="capitalize" variant={variants[status] || "default"}>
      {status}
    </Badge>
  );
}

export default function App() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState("");
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [recentCredits, setRecentCredits] = useState<Transaction[]>([]);
  const [recentDebits, setRecentDebits] = useState<Transaction[]>([]);
  const [payoutHistory, setPayoutHistory] = useState<PayoutResponse[]>([]);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const activeMerchant = useMemo(
    () => merchants.find((item) => item.username === selectedMerchant),
    [merchants, selectedMerchant],
  );

  const merchantHeaders = selectedMerchant
    ? { "X-Merchant-Username": selectedMerchant }
    : undefined;

  const fetchMerchants = async () => {
    const response = await fetch("/api/v1/merchants");
    if (!response.ok) throw new Error("Failed to fetch merchants");
    const data: Merchant[] = await response.json();
    setMerchants(data);
    setSelectedMerchant((current) => current || data[0]?.username || "");
  };

  const fetchDashboard = async () => {
    if (!selectedMerchant) return;
    const response = await fetch("/api/v1/dashboard", {
      headers: merchantHeaders,
    });
    if (!response.ok) throw new Error("Failed to fetch dashboard");
    const data = await response.json();
    setMerchant(data);
    setRecentCredits(data.recent_credits || []);
    setRecentDebits(data.recent_debits || []);
  };

  const fetchPayoutHistory = async () => {
    if (!selectedMerchant) return;
    const response = await fetch("/api/v1/payouts/history", {
      headers: merchantHeaders,
    });
    if (!response.ok) throw new Error("Failed to fetch payout history");
    setPayoutHistory(await response.json());
  };

  const refreshAll = async () => {
    setRefreshing(true);
    try {
      await fetchMerchants();
      await Promise.all([fetchDashboard(), fetchPayoutHistory()]);
    } catch (err) {
      console.error("Failed to refresh dashboard:", err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchMerchants().catch((err) =>
      console.error("Failed to fetch merchants:", err),
    );
  }, []);

  useEffect(() => {
    setMerchant(null);
    setRecentCredits([]);
    setRecentDebits([]);
    setPayoutHistory([]);
    setError("");
    setSuccess("");

    refreshAll();
    const interval = setInterval(refreshAll, 5000);
    return () => clearInterval(interval);
  }, [selectedMerchant]);

  const handlePayoutRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const amountPaise = Math.round(Number.parseFloat(amount) * 100);
      const response = await fetch("/api/v1/payouts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
          ...merchantHeaders,
        },
        body: JSON.stringify({
          amount_paise: amountPaise,
          bank_account_id: bankAccountId,
        }),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Failed to create payout");

      setSuccess(`Payout ${data.id.slice(0, 8)} created and funds are held.`);
      setAmount("");
      setBankAccountId("");
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const balanceCards = [
    {
      title: "Available",
      value: formatPaise(merchant?.available_balance_paise),
      detail: "Ready for payout",
      icon: WalletCards,
      tone: "text-emerald-300",
    },
    {
      title: "Held",
      value: formatPaise(merchant?.held_balance_paise),
      detail: "Pending bank settlement",
      icon: Clock3,
      tone: "text-amber-300",
    },
    {
      title: "Total",
      value: formatPaise(merchant?.total_balance_paise),
      detail: "Available plus held",
      icon: CircleDollarSign,
      tone: "text-sky-300",
    },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[2rem] border border-border/70 bg-card/70 p-5 shadow-2xl shadow-black/20 backdrop-blur md:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex size-9 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                  <ShieldCheck className="size-5" />
                </div>
                <Badge
                  variant="outline"
                  className="border-primary/30 text-primary"
                >
                  Live ledger
                </Badge>
              </div>
              <div>
                <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-4xl">
                  Playto Payouts
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  Monitor merchant balances, holds, payout attempts, and bank
                  settlement state from one synced console.
                </p>
              </div>
            </div>

            <div className="grid gap-2 sm:min-w-80">
              <Label
                htmlFor="merchantAccount"
                className="text-muted-foreground"
              >
                Merchant account
              </Label>
              <Select
                value={selectedMerchant}
                onValueChange={setSelectedMerchant}
                disabled={merchants.length === 0}
              >
                <SelectTrigger
                  id="merchantAccount"
                  className="h-12 w-full rounded-2xl border-border/80 bg-background/80 px-4"
                >
                  <SelectValue placeholder="Select merchant" />
                </SelectTrigger>
                <SelectContent align="end" className="rounded-2xl">
                  {merchants.map((item) => (
                    <SelectItem key={item.username} value={item.username!}>
                      <span className="font-medium">{item.username}</span>
                      <span className="text-muted-foreground">
                        {formatPaise(item.available_balance_paise)}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {activeMerchant?.email && (
                <p className="text-xs text-muted-foreground">
                  {activeMerchant.email}
                </p>
              )}
            </div>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {balanceCards.map((item) => {
            const Icon = item.icon;
            return (
              <Card
                key={item.title}
                className="rounded-2xl border border-border/70 bg-card/80 shadow-xl shadow-black/10"
              >
                <CardHeader className="pb-0">
                  <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Icon className={`size-4 ${item.tone}`} />
                    {item.title} balance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-semibold tracking-normal">
                    {item.value}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {item.detail}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <Card className="rounded-2xl border border-border/70 bg-card/80 shadow-xl shadow-black/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BanknoteArrowDown className="size-5 text-primary" />
                Request payout
              </CardTitle>
              <CardDescription>
                Funds are held immediately and settled by the worker.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePayoutRequest} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="amount">Amount</Label>
                  <Input
                    id="amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="0.00"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    required
                    className="h-11 rounded-2xl bg-background/80 text-lg"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bankAccount">Bank account ID</Label>
                  <Input
                    id="bankAccount"
                    type="text"
                    placeholder="bank_acc_..."
                    value={bankAccountId}
                    onChange={(event) => setBankAccountId(event.target.value)}
                    required
                    className="h-11 rounded-2xl bg-background/80"
                  />
                </div>

                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="size-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                {success && (
                  <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-100">
                    <CheckCircle className="size-4 text-emerald-300" />
                    <AlertDescription>{success}</AlertDescription>
                  </Alert>
                )}

                <Button
                  type="submit"
                  disabled={loading || !selectedMerchant}
                  className="h-11 w-full rounded-2xl"
                >
                  {loading ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <ArrowDownToLine className="mr-2 size-4" />
                  )}
                  {loading ? "Creating hold..." : "Request payout"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border border-border/70 bg-card/80 shadow-xl shadow-black/10">
            <CardHeader>
              <CardTitle>Recent ledger activity</CardTitle>
              <CardDescription>
                Latest credits and payout debits for the selected merchant.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-5 lg:grid-cols-2">
              <ActivityTable
                emptyText="No credits yet"
                rows={recentCredits}
                title="Credits"
                positive
              />
              <ActivityTable
                emptyText="No payout debits yet"
                rows={recentDebits}
                title="Debits"
              />
            </CardContent>
          </Card>
        </section>

        <Card className="rounded-2xl border border-border/70 bg-card/80 shadow-xl shadow-black/10">
          <CardHeader>
            <div>
              <CardTitle>Payout history</CardTitle>
              <CardDescription>
                Live status updates refresh every five seconds.
              </CardDescription>
            </div>
            <CardAction>
              <Button
                variant="outline"
                size="sm"
                onClick={refreshAll}
                disabled={refreshing}
                className="rounded-2xl"
              >
                <RefreshCw
                  className={`mr-2 size-4 ${refreshing ? "animate-spin" : ""}`}
                />
                Refresh
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {payoutHistory.length === 0 ? (
              <EmptyState text="No payout history yet" />
            ) : (
              <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/45">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>ID</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Bank account</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {payoutHistory.map((payout) => (
                      <TableRow key={payout.id}>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {payout.id.slice(0, 8)}
                        </TableCell>
                        <TableCell className="font-medium text-rose-300">
                          -{formatPaise(payout.amount_paise)}
                        </TableCell>
                        <TableCell>{payout.bank_account_id}</TableCell>
                        <TableCell>{formatStatus(payout.status)}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDate(payout.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function ActivityTable({
  emptyText,
  positive = false,
  rows,
  title,
}: {
  emptyText: string;
  positive?: boolean;
  rows: Transaction[];
  title: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        <Badge variant="outline">{rows.length}</Badge>
      </div>
      {rows.length === 0 ? (
        <EmptyState text={emptyText} compact />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/45">
          <Table>
            <TableBody>
              {rows.slice(0, 5).map((row) => (
                <TableRow key={row.id}>
                  <TableCell
                    className={`font-medium ${
                      positive ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {positive ? "+" : "-"}
                    {formatPaise(row.amount_paise)}
                  </TableCell>
                  <TableCell className="max-w-40 truncate text-muted-foreground">
                    {row.description || row.bank_account_id || "Payout"}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatDate(row.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function EmptyState({
  compact = false,
  text,
}: {
  compact?: boolean;
  text: string;
}) {
  return (
    <div
      className={`flex items-center justify-center rounded-2xl border border-dashed border-border/80 bg-background/35 text-sm text-muted-foreground ${
        compact ? "h-28" : "h-40"
      }`}
    >
      <Landmark className="mr-2 size-4" />
      {text}
    </div>
  );
}
