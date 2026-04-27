import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, AlertCircle, CheckCircle, RefreshCw } from "lucide-react";

interface Merchant {
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

function formatPaise(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toFixed(2)}`;
}

function formatStatus(status: string): React.ReactNode {
  const variants: Record<
    string,
    "default" | "secondary" | "destructive" | "outline" | "ghost" | "link"
  > = {
    pending: "secondary",
    processing: "outline",
    completed: "default",
    failed: "destructive",
  };
  return <Badge variant={variants[status] || "default"}>{status}</Badge>;
}

export default function App() {
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [recentCredits, setRecentCredits] = useState<Transaction[]>([]);
  const [recentDebits, setRecentDebits] = useState<Transaction[]>([]);
  const [payoutHistory, setPayoutHistory] = useState<PayoutResponse[]>([]);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fetchDashboard = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/dashboard", {
        headers: {
          Authorization: "Bearer demo-token", // In real app, use actual auth
        },
      });
      if (!response.ok) throw new Error("Failed to fetch dashboard");
      const data = await response.json();
      setMerchant(data);
      setRecentCredits(data.recent_credits || []);
      setRecentDebits(data.recent_debits || []);
    } catch (err) {
      console.error("Failed to fetch dashboard:", err);
    }
  };

  // Fetch payout history
  const fetchPayoutHistory = async () => {
    try {
      const response = await fetch("/api/v1/payouts/history", {
        headers: {
          Authorization: "Bearer demo-token",
        },
      });
      if (!response.ok) throw new Error("Failed to fetch payout history");
      const data = await response.json();
      setPayoutHistory(data);
    } catch (err) {
      console.error("Failed to fetch payout history:", err);
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchPayoutHistory();

    // Poll for updates every 5 seconds
    const interval = setInterval(() => {
      fetchDashboard();
      fetchPayoutHistory();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handlePayoutRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const amountPaise = Math.round(parseFloat(amount) * 100);
      const idempotencyKey = crypto.randomUUID();

      const response = await fetch("/api/v1/payouts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
          Authorization: "Bearer demo-token",
        },
        body: JSON.stringify({
          amount_paise: amountPaise,
          bank_account_id: bankAccountId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to create payout");
      }

      setSuccess(`Payout created successfully! ID: ${data.id}`);
      setAmount("");
      setBankAccountId("");

      // Refresh data
      fetchDashboard();
      fetchPayoutHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Playto Payout Dashboard
          </h1>
          <p className="text-gray-600 mt-2">
            Manage your balance and request payouts
          </p>
        </header>

        {/* Balance Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-gray-600">
                Available Balance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {merchant
                  ? formatPaise(merchant.available_balance_paise)
                  : "₹0.00"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-gray-600">
                Held Balance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-orange-600">
                {merchant ? formatPaise(merchant.held_balance_paise) : "₹0.00"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Balance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600">
                {merchant ? formatPaise(merchant.total_balance_paise) : "₹0.00"}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Payout Request Form */}
          <Card>
            <CardHeader>
              <CardTitle>Request Payout</CardTitle>
              <CardDescription>
                Enter amount and bank account details
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePayoutRequest} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="amount">Amount (₹)</Label>
                  <Input
                    id="amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="Enter amount in rupees"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bankAccount">Bank Account ID</Label>
                  <Input
                    id="bankAccount"
                    type="text"
                    placeholder="Enter bank account ID"
                    value={bankAccountId}
                    onChange={(e) => setBankAccountId(e.target.value)}
                    required
                  />
                </div>

                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                {success && (
                  <Alert
                    variant="default"
                    className="bg-green-50 border-green-200"
                  >
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      {success}
                    </AlertDescription>
                  </Alert>
                )}

                <Button type="submit" disabled={loading} className="w-full">
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {loading ? "Processing..." : "Request Payout"}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Recent Transactions */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Transactions</CardTitle>
              <CardDescription>
                Credits and debits from the last 24 hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">
                    Recent Credits
                  </h4>
                  {recentCredits.length === 0 ? (
                    <p className="text-gray-400 text-sm">No recent credits</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Amount</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {recentCredits.map((credit) => (
                          <TableRow key={credit.id}>
                            <TableCell className="text-green-600 font-medium">
                              +{formatPaise(credit.amount_paise)}
                            </TableCell>
                            <TableCell>
                              {credit.description || "Credit"}
                            </TableCell>
                            <TableCell className="text-gray-500">
                              {new Date(credit.created_at).toLocaleDateString()}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">
                    Recent Debits
                  </h4>
                  {recentDebits.length === 0 ? (
                    <p className="text-gray-400 text-sm">No recent debits</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {recentDebits.map((debit) => (
                          <TableRow key={debit.id}>
                            <TableCell className="text-red-600 font-medium">
                              -{formatPaise(debit.amount_paise)}
                            </TableCell>
                            <TableCell>
                              {formatStatus(debit.status || "pending")}
                            </TableCell>
                            <TableCell className="text-gray-500">
                              {new Date(debit.created_at).toLocaleDateString()}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Payout History */}
        <Card className="mt-8">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Payout History</CardTitle>
                <CardDescription>
                  All payout requests and their status
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchPayoutHistory}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {payoutHistory.length === 0 ? (
              <p className="text-gray-400 text-center py-8">
                No payout history yet
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Bank Account</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payoutHistory.map((payout) => (
                    <TableRow key={payout.id}>
                      <TableCell className="font-mono text-sm">
                        {payout.id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="text-red-600 font-medium">
                        -{formatPaise(payout.amount_paise)}
                      </TableCell>
                      <TableCell>{payout.bank_account_id}</TableCell>
                      <TableCell>{formatStatus(payout.status)}</TableCell>
                      <TableCell className="text-gray-500">
                        {new Date(payout.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
