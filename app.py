########################################################
#  Author: Anton1                                      #
#  Details: Small Flet-based application allowing the  #
#  user to add assets and display the total portfolio  #
#  value over time in a graph by fetching prices and   #
#  metadata from Yahoo Finance.                        #
########################################################

# Import Flet for building the graphical user interface.
import flet as ft

# Import datetime for date handling.
import datetime

# Import yfinance to retrieve prices, metadata, and FX rates.
import yfinance as yf

# Import pandas for time series manipulation and calculations.
import pandas as pd


# Create the main application entry point.
def main(page: ft.Page):
    """Build the UI and wire up handlers for assets, charts, and dialogs."""
    page.title = "Portfolio Visualizer"
    page.bgcolor = ft.Colors.BLACK54
    page.scroll = ft.ScrollMode.AUTO

    # List to store assets added by the user.
    assets = []

    # Text displaying the total portfolio value.
    total_worth_value_text = ft.Text(
        "CHF 0.00",
        size=18,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
    )

    # Text displaying the total portfolio percentage gain or loss.
    total_gain_pct_text = ft.Text(
        "",
        size=12,
        color=ft.Colors.WHITE70,
        weight=ft.FontWeight.BOLD,
    )

    # Text displaying the total portfolio profit.
    total_profit_text = ft.Text(
        "",
        size=12,
        color=ft.Colors.WHITE70,
    )

    # Line chart showing the total portfolio value over time.
    total_worth_chart = ft.LineChart(
        data_series=[],
        min_y=0,
        expand=True,
        tooltip_bgcolor=ft.Colors.GREY_800,
        left_axis=ft.ChartAxis(labels_size=40),
        bottom_axis=ft.ChartAxis(labels_size=32),
    )

    # Column displaying the Y axis labels left to the chart.
    y_axis_labels_col = ft.Column(
        width=80,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        horizontal_alignment=ft.CrossAxisAlignment.END,
        controls=[],
    )

    # Row displaying the X axis labels under the chart.
    x_axis_labels_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[],
    )

    # Date picker overlay used to select asset purchase dates.
    date_picker = ft.DatePicker(last_date=datetime.date.today())
    page.overlay.append(date_picker)

    # Create an AlertDialog, which is later used for invalid inputs by the user.
    def open_error_dialog(title: str, message: str):
        """
        Open a modal dialog to display an error message
        and prevent interaction until closed.
        """
        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=15),
            title=ft.Text(
                title,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.RED_ACCENT,
            ),
            bgcolor=ft.Colors.GREY_900,
            content=ft.Text(message, color=ft.Colors.WHITE70),
            actions=[
                ft.TextButton(
                    "OK",
                    on_click=lambda e: page.close(dlg),
                    style=ft.ButtonStyle(color=ft.Colors.WHITE),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)
        page.update()

    # Convert values to float to handle calculations.
    def to_float(value, default=0.0) -> float:
        """
        Convert values to float and return default
        if conversion fails.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # Convert decimal values into percentage for easier readability.
    def format_pct(value: float) -> str:
        """
        Format decimal number as a percentage string
        and add a plus sign for positive values.
        """
        return f"+{value:.2%}" if value >= 0 else f"{value:.2%}"

    # Display green or red color for the value for easier readability.
    def signed_color(value: float):
        """Return a green or red color based on the value sign."""
        return ft.Colors.GREEN_ACCENT if value >= 0 else ft.Colors.RED_ACCENT

    # Round values and display them in CHF for easier readability.
    def format_signed_chf(value: float, comma: bool = True) -> str:
        """Format value to CHF and add a plus sign for positive values."""
        fmt = f"{value:,.2f}" if comma else f"{value:.2f}"
        return f"CHF +{fmt}" if value >= 0 else f"CHF {fmt}"

    # Fetch closing prices as a series from yf for later use in the graph.
    def download_close(ticker: str, **kwargs) -> pd.Series | None:
        """
        Download closing prices for the user ticker from Yahoo Finance
        and return a cleaned pandas Series indexed by date.
        """
        try:
            hist = yf.download(
                ticker, progress=True, auto_adjust=False, threads=False, **kwargs
            )
        except Exception:
            return None

        if hist is None or len(hist) == 0 or "Close" not in hist.columns:
            return None

        close = hist["Close"]
        if isinstance(close, pd.DataFrame):
            close = close[ticker] if ticker in close.columns else close.iloc[:, 0]

        close = close.dropna()
        if len(close) == 0:
            return None

        close.index = pd.to_datetime(close.index).normalize()
        return close

    # Correct yf-specific currency formatting for easier readability.
    def _normalize_ccy(ccy: str | None) -> str:
        """Normalize currency code and handle Yahoo-specific oddities."""
        if not ccy:
            return "CHF"
        ccy = ccy.strip()

        if ccy == "GBp":
            return "GBP"
        return ccy

    # Fetch inputted ticker's currency for later FX conversion.
    def get_ticker_currency(ticker_symbol: str) -> str:
        """Retrieve the ticker's currency and default to CHF on failure."""
        try:
            ccy = yf.Ticker(ticker_symbol).info.get("currency")
            return _normalize_ccy(ccy)
        except Exception:
            return "CHF"

    # Convert ticker's currency to CHF.
    def get_fx_rate_to_chf(from_ccy: str) -> float:
        """Fetch the latest FX rate to CHF for the ticker's currency."""
        from_ccy = _normalize_ccy(from_ccy)
        if from_ccy == "CHF":
            return 1.0

        fx_ticker = f"{from_ccy}CHF=X"
        close = download_close(fx_ticker, period="5d")
        if close is None:
            raise ValueError(f"Could not fetch FX rate for {fx_ticker}")

        return float(close.iloc[-1])

    # Fetch FX prices as a series for later use in the graph.
    def get_fx_series_to_chf(
        from_ccy: str, start_date: datetime.date, end_date: datetime.date
    ) -> pd.Series:
        """Fetch an FX series to CHF for the date range."""
        from_ccy = _normalize_ccy(from_ccy)
        if from_ccy == "CHF":
            idx = pd.date_range(
                pd.Timestamp(start_date), pd.Timestamp(end_date), freq="D"
            )
            return pd.Series(1.0, index=idx)

        fx_ticker = f"{from_ccy}CHF=X"
        fx = download_close(fx_ticker, start=start_date, end=end_date)
        if fx is None:
            raise ValueError(f"Could not fetch FX series for {fx_ticker}")

        return fx

    # Fetch most recent ticker's price so it can later be used calculations.
    def get_current_price(ticker_symbol: str) -> float:
        """Return the latest price for a ticker, converted to CHF."""
        t = yf.Ticker(ticker_symbol)
        info = t.info

        price = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )

        # Fallback to historical prices in case market is closed.
        if price is None:
            hist = t.history(period="5d")
            if not hist.empty and "Close" in hist.columns:
                price = hist["Close"].dropna().iloc[-1]

        if price is None:
            raise ValueError(f"No price data available for ticker {ticker_symbol}")

        price = float(price)

        ccy = _normalize_ccy(info.get("currency"))

        if ccy == "GBP" and info.get("currency") == "GBp":
            price = price / 100.0

        fx = get_fx_rate_to_chf(ccy)
        return price * fx

    # Fetch the oldest price date for the ticker to prevent invalid inputted dates.
    def get_first_price_date(ticker_symbol: str):
        """
        Return the first available price date for the ticker
        to check if the user's purchase date is valid.
        """
        try:
            info = yf.Ticker(ticker_symbol).info or {}
            epoch = info.get("firstTradeDateEpochUtc") or info.get(
                "firstTradeDateEpochUTC"
            )
            if epoch:
                return datetime.date.fromtimestamp(int(epoch))
        except Exception:
            pass

        close = download_close(ticker_symbol, period="max")
        if close is None:
            return None

        return close.index.min().date()

    # Fetch ticker's name from yf to later display it.
    def get_ticker_name(ticker: str) -> str | None:
        """Return the ticker's long name when available."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("longName")
        except Exception:
            return None

    # Fetch ticker's type from yf to later display it.
    def get_asset_type(ticker: str) -> str:
        """Fetch and return a readable asset type."""
        try:
            info = yf.Ticker(ticker).info
            qt = info.get("quoteType")

            if qt == "EQUITY":
                return "Stock"
            if qt == "ETF":
                return "ETF"
            if qt == "MUTUALFUND":
                return "Fund"
            if qt == "CRYPTOCURRENCY":
                return "Crypto"
            if qt == "INDEX":
                return "Index"

            return "Other"
        except Exception:
            return "Unknown"

    def reset_total_worth(clear_summary: bool = True):
        """Clear chart data and reset portfolio total values."""
        total_worth_value_text.value = "CHF 0.00"
        if clear_summary:
            total_gain_pct_text.value = ""
            total_profit_text.value = ""
            total_gain_pct_text.color = ft.Colors.WHITE70
            total_profit_text.color = ft.Colors.WHITE70
        total_worth_chart.data_series = []
        total_worth_chart.min_y = 0
        total_worth_chart.max_y = 1
        total_worth_chart.min_x = 0
        total_worth_chart.max_x = 1
        y_axis_labels_col.controls = []
        x_axis_labels_row.controls = []
        total_worth_chart.left_axis = ft.ChartAxis(show_labels=False)
        total_worth_chart.bottom_axis = ft.ChartAxis(show_labels=False)

    # Compute the total portfolio value over time.
    def update_total_worth_graph():
        """
        Compute the total portfolio values over time, convert
        all assets to CHF, align dates, update the chart.
        """

        # Reset the chart in case no assets are present.
        if len(assets) == 0:
            reset_total_worth()
            return

        # Use the earliest purchase date as start date.
        purchase_dates = [
            a.get("purchase_date") for a in assets if a.get("purchase_date")
        ]
        start_date = (
            min(purchase_dates)
            if purchase_dates
            else (datetime.date.today() - datetime.timedelta(days=365))
        )
        end_date = datetime.date.today() + datetime.timedelta(days=1)

        series_list = []
        for a in assets:
            ticker = a.get("ticker")
            # Skip invalid assets.
            if not ticker:
                continue

            shares = to_float(a.get("shares"))
            if shares <= 0:
                continue

            pdate = a.get("purchase_date")
            p_ts = pd.Timestamp(pdate) if pdate else None

            # Download historical prices.
            close = download_close(ticker, start=start_date, end=end_date)
            if close is None:
                continue

            # Determine the currency of the asset.
            asset_ccy = get_ticker_currency(ticker)

            # Convert prices to CHF if needed.
            if asset_ccy != "CHF":
                fx = get_fx_series_to_chf(asset_ccy, start_date, end_date)

                # Align FX series with price series.
                fx = fx.reindex(close.index).ffill()
                close = close * fx

            value = close * shares

            # Trim series to purchase date.
            if p_ts is not None:
                value = value[value.index >= p_ts]

                # Ensure first value matches the purchase price.
                purchase_price = to_float(a.get("price"))
                if purchase_price > 0:
                    value.loc[p_ts] = shares * purchase_price
                    value = value.sort_index()

            if len(value) == 0:
                continue

            series_list.append(value.rename(ticker))

        # Reset the chart if no valid series exist.
        if len(series_list) == 0:
            reset_total_worth()
            return

        # Align all assets on the same date index.
        combined = pd.concat(series_list, axis=1).sort_index().ffill()
        total = combined.fillna(0).sum(axis=1)

        today_ts = pd.Timestamp(datetime.date.today())
        if len(total) > 0 and total.index.max() < today_ts:
            latest_total = 0.0
            for a in assets:
                shares = to_float(a.get("shares"))
                if shares <= 0:
                    continue

                pdate = a.get("purchase_date")
                if pdate and today_ts < pd.Timestamp(pdate):
                    continue

                current_price = to_float(a.get("current_price"))
                latest_total += shares * current_price

            total.loc[today_ts] = latest_total
            total = total.sort_index()

        if len(total) == 0:
            reset_total_worth()
            return

        # Compute summary values.
        last_value = float(total.iloc[-1])
        total_worth_value_text.value = f"CHF {last_value:,.2f}"

        total_cost = 0.0
        total_current = 0.0

        for a in assets:
            shares = to_float(a.get("shares"))
            if shares <= 0:
                continue

            purchase_price = to_float(a.get("price"))
            current_price = to_float(a.get("current_price"))
            total_cost += shares * purchase_price
            total_current += shares * current_price

        # Compute profit/loss and gain/loss in percentage
        total_profit = total_current - total_cost
        total_pct = (total_profit / total_cost) if total_cost > 0 else 0.0

        total_gain_pct_text.value = format_pct(total_pct)
        total_gain_pct_text.color = signed_color(total_profit)

        total_profit_text.value = format_signed_chf(total_profit, comma=True)
        total_profit_text.color = signed_color(total_profit)

        dates = total.index.to_list()
        n = len(dates)
        values = total.values.astype(float)

        points = [ft.LineChartDataPoint(i, float(v)) for i, v in enumerate(values)]

        min_val = float(values.min())
        max_val = float(values.max())
        rng_val = max_val - min_val

        if abs(rng_val) < 1e-9:
            min_y = min_val - 1
            max_y = max_val + 1
        else:
            pad = 0.05 * rng_val
            min_y = min_val - pad
            max_y = max_val + pad

        # Update the chart series styling and data points.
        total_worth_chart.data_series = [
            ft.LineChartData(
                data_points=points,
                curved=True,
                stroke_width=2,
                color=ft.Colors.AMBER_200,
                below_line_gradient=ft.LinearGradient(
                    begin=ft.alignment.top_center,
                    end=ft.alignment.bottom_center,
                    colors=[
                        ft.Colors.with_opacity(0.22, ft.Colors.AMBER_200),
                        ft.Colors.with_opacity(0.00, ft.Colors.AMBER_200),
                    ],
                    stops=[0.0, 1.0],
                ),
            )
        ]

        total_worth_chart.min_x = 0
        total_worth_chart.max_x = max(1, n - 1)
        total_worth_chart.min_y = min_y
        total_worth_chart.max_y = max_y

        # Hide built-in axis labels.
        total_worth_chart.left_axis = ft.ChartAxis(show_labels=False)
        total_worth_chart.bottom_axis = ft.ChartAxis(show_labels=False)

        # Build custom Y labels.
        y_ticks = 8
        rng = max_y - min_y
        step = rng / y_ticks if rng > 0 else 1.0
        y_axis_labels_col.controls = [
            ft.Text(
                f"CHF {(min_y + i * step):,.2f}",
                size=10,
                color=ft.Colors.WHITE70,
                no_wrap=True,
            )
            for i in reversed(range(y_ticks + 1))
        ]

        # Build custom X labels.
        x_labels_count = 8

        # Handle special case of a single date.
        if n <= 1:
            x_axis_labels_row.controls = [
                ft.Text(
                    pd.Timestamp(dates[0]).strftime("%d/%m/%y"),
                    size=10,
                    color=ft.Colors.WHITE70,
                )
            ]
        else:
            # Spread labels evenly across the full date range.
            start_ts = pd.Timestamp(dates[0]).normalize()
            end_ts = pd.Timestamp(dates[-1]).normalize()
            total_days = (end_ts.date() - start_ts.date()).days
            denom = x_labels_count - 1

            labels = []
            for i in range(x_labels_count):
                day_offset = int(round(total_days * i / denom))
                label_date = start_ts.date() + datetime.timedelta(days=day_offset)
                labels.append(
                    ft.Text(
                        label_date.strftime("%d/%m/%y"),
                        size=10,
                        color=ft.Colors.WHITE70,
                        no_wrap=True,
                    )
                )
            x_axis_labels_row.controls = labels

    # Column containing the holdings.
    assets_column = ft.Column(spacing=10)

    def refresh_assets():
        """Rebuild the holdings list and refresh the chart."""
        update_total_worth_graph()
        assets_column.controls.clear()

        # Show "No assets" if no assets exists
        if len(assets) == 0:
            assets_column.controls.append(ft.Text("No assets"))
            page.update()
            return

        # Build a container for each added asset and compute respective values.
        for a in assets:
            gain = to_float(a.get("percentage gain"))
            profit = to_float(a.get("profit gain"))
            shares = to_float(a.get("shares"))
            price = to_float(a.get("price"))
            current_price = to_float(a.get("current_price"))
            purchase_date_str = a.get("purchase_date_str", "")

            # Create the asset card container.
            assets_column.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.GREY_900,
                    border=ft.border.all(1, ft.Colors.GREY_800),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        f'{a["ticker"]} | {a["name"]}',
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.AMBER_200,
                                    ),
                                    ft.Row(
                                        controls=[
                                            ft.Container(
                                                padding=ft.padding.symmetric(
                                                    horizontal=12, vertical=1
                                                ),
                                                alignment=ft.alignment.center,
                                                bgcolor=ft.Colors.GREY_700,
                                                border_radius=12,
                                                content=ft.Text(
                                                    a["type"],
                                                    color=ft.Colors.WHITE,
                                                    size=11,
                                                ),
                                            ),
                                            ft.Container(
                                                bgcolor=ft.Colors.GREY_800,
                                                border_radius=12,
                                                height=20,
                                                width=20,
                                                alignment=ft.alignment.center,
                                                content=ft.IconButton(
                                                    icon=ft.Icons.CLOSE,
                                                    icon_color=ft.Colors.RED_ACCENT,
                                                    icon_size=12,
                                                    padding=0,
                                                    on_click=lambda e, t=a[
                                                        "ticker"
                                                    ]: delete_asset(t),
                                                ),
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(purchase_date_str),
                                            ft.Text(
                                                f"{shares:.2f} {'share' if round(shares, 2) <= 1 else 'shares'}"
                                            ),
                                        ],
                                    ),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    ft.Text(
                                                        "Purchase price     ",
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"CHF {price:.2f}",
                                                    ),
                                                ],
                                            ),
                                            ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    ft.Text(
                                                        "Current price      ",
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"CHF {current_price:.2f}",
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    ft.Text(
                                                        format_pct(gain),
                                                        color=signed_color(gain),
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                ],
                                            ),
                                            ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    ft.Text(
                                                        format_signed_chf(
                                                            profit, comma=False
                                                        ),
                                                        color=signed_color(profit),
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            )
        page.update()

    def delete_asset(ticker: str):
        """Remove the selected asset from the portfolio refresh the display."""
        for i, a in enumerate(assets):
            if a["ticker"] == ticker:
                assets.pop(i)
                break
        refresh_assets()

    def add_asset(e):
        """Open a dialog allowing the user to add a new asset."""

        # Defining "Ticker" and "Label" fields for the "Add asset" dialog.
        ticker_field = ft.TextField(
            label="Ticker",
            border_color=ft.Colors.GREY_700,
            focused_border_color=ft.Colors.AMBER_200,
            cursor_color=ft.Colors.AMBER_200,
            label_style=ft.TextStyle(
                color=ft.Colors.WHITE70,
                size=13,
            ),
        )
        shares_field = ft.TextField(
            label="Shares",
            border_color=ft.Colors.GREY_700,
            focused_border_color=ft.Colors.AMBER_200,
            cursor_color=ft.Colors.AMBER_200,
            label_style=ft.TextStyle(
                color=ft.Colors.WHITE70,
                size=13,
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(
                allow=True,
                regex_string=r"^[0-9.]*$",
                replacement_string="",
            ),
        )
        price_field = ft.TextField(
            label="Price per share (CHF)",
            border_color=ft.Colors.GREY_700,
            focused_border_color=ft.Colors.AMBER_200,
            cursor_color=ft.Colors.AMBER_200,
            label_style=ft.TextStyle(
                color=ft.Colors.WHITE70,
                size=13,
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(
                allow=True,
                regex_string=r"^[0-9.]*$",
                replacement_string="",
            ),
        )

        def on_field_change(e):
            """Validate fields without showing errors while typing."""
            validate_fields(False)

        for field in (ticker_field, shares_field, price_field):
            field.on_change = on_field_change

        # Dialog to pick a date.
        selected_purchase_date = {"value": None}

        def on_date_selected(e):
            """Update the selected date and button label."""
            selected_purchase_date["value"] = date_picker.value
            if selected_purchase_date["value"]:
                date_btn.text = selected_purchase_date["value"].strftime("%d/%m/%y")
                validate_fields(False)
            else:
                date_btn.text = "Select date"
            page.update()

        date_picker.on_change = on_date_selected

        def open_date_picker(e):
            """Open the date picker overlay."""
            date_picker.open = True
            page.update()

        # Button to select a purchase date.
        date_btn = ft.ElevatedButton(
            text="Select date",
            bgcolor=ft.Colors.GREY_800,
            color=ft.Colors.WHITE,
            icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
            on_click=open_date_picker,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                color=ft.Colors.AMBER_200,
                shape=ft.RoundedRectangleBorder(radius=18),
                side=ft.BorderSide(width=1, color=ft.Colors.TRANSPARENT),
            ),
        )

        def validate_fields(show_errors: bool):
            """Validate dialog inputs and optionally show error styling."""
            ticker = (ticker_field.value or "").strip()
            shares_raw = (shares_field.value or "").strip()
            price_raw = (price_field.value or "").strip()
            date_ok = selected_purchase_date["value"] is not None

            ticker_ok = bool(ticker)
            shares_ok = to_float(shares_raw) > 0
            price_ok = to_float(price_raw) > 0
            fields = (
                (ticker_field, ticker_ok),
                (shares_field, shares_ok),
                (price_field, price_ok),
            )

            if show_errors:
                for field, ok in fields:
                    field.error_text = None if ok else "Required"

                date_btn.style.side = ft.BorderSide(
                    1,
                    ft.Colors.GREY_700 if date_ok else ft.Colors.RED_200,
                )

            else:
                # clear visuals while typing.
                for field, _ in fields:
                    field.error_text = None

                date_btn.style.side = ft.BorderSide(1, ft.Colors.TRANSPARENT)

            page.update()
            return ticker_ok and shares_ok and price_ok and date_ok

        def on_add_click(e):
            """Validate inputs and add the asset to the portfolio."""
            if not validate_fields(True):
                return
            ticker = (ticker_field.value or "").strip().upper()
            purchase_date = selected_purchase_date["value"]

            if isinstance(purchase_date, datetime.datetime):
                purchase_date = purchase_date.date()

            if not purchase_date:
                open_error_dialog("Invalid date", "Please select a purchase date.")
                return
            if purchase_date > datetime.date.today():
                open_error_dialog(
                    "Invalid date", "Purchase date cannot be in the future."
                )
                return

            shares = to_float(shares_field.value)
            price = to_float(price_field.value)
            if shares <= 0 or price <= 0:
                open_error_dialog(
                    "Invalid input", "Shares and price must be valid numbers."
                )
                return

            try:
                current_price = get_current_price(ticker)
            except Exception:
                ticker_field.error_text = "Invalid ticker"
                page.update()
                open_error_dialog(
                    "Invalid ticker",
                    f'Could not fetch price data for "{ticker}". Please check the ticker symbol and try again.',
                )
                return

            first_dt = get_first_price_date(ticker)
            if first_dt and purchase_date < first_dt:
                open_error_dialog(
                    "Invalid date",
                    f'{ticker} has price history only from {first_dt.strftime("%d/%m/%y")}. Please select a later purchase date.',
                )
                return

            purchase_date_str = (
                purchase_date.strftime("%d/%m/%y") if purchase_date else "Not set"
            )
            profit = shares * (current_price - price)

            # Add the asset to the portfolio.
            assets.append(
                {
                    "ticker": ticker,
                    "name": get_ticker_name(ticker),
                    "type": get_asset_type(ticker),
                    "shares": shares,
                    "price": price,
                    "current_price": current_price,
                    "purchase_date": purchase_date,
                    "purchase_date_str": purchase_date_str,
                    "percentage gain": (current_price - price) / price,
                    "profit gain": profit,
                }
            )

            page.close(add_asset_dialog)
            refresh_assets()

        # "Add asset" dialog with the possibility to enter asset details.
        add_asset_dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=15),
            title=ft.Text(
                "Asset details",
                size=25,
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=ft.Colors.GREY_900,
            content=ft.Container(
                width=600,
                height=295,
                padding=20,
                content=ft.Column(
                    controls=[
                        ticker_field,
                        shares_field,
                        price_field,
                        date_btn,
                    ]
                ),
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: page.close(add_asset_dialog),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                    ),
                ),
                ft.ElevatedButton(
                    text="Add",
                    on_click=on_add_click,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.AMBER_200,
                        color=ft.Colors.BLACK,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.open(add_asset_dialog)
        page.update()

    # Header row including title and the "add asset" button.
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                "Portfolio",
                size=48,
                color=ft.Colors.AMBER_200,
                weight=ft.FontWeight.BOLD,
            ),
            ft.ElevatedButton(
                text="Add asset",
                icon=ft.Icons.ADD,
                on_click=add_asset,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.AMBER_200,
                    color=ft.Colors.BLACK,
                ),
            ),
        ],
    )

    # Container containing the graph of the total portfolio and the summary values.
    graph = ft.Container(
        bgcolor=ft.Colors.GREY_900,
        padding=25,
        height=350,
        width=900,
        border_radius=12,
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(
                            "Total worth",
                            size=20,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=2,
                            controls=[
                                total_worth_value_text,
                                total_gain_pct_text,
                                total_profit_text,
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        y_axis_labels_col,
                        ft.Container(expand=True, content=total_worth_chart),
                    ],
                ),
                # Manual x-axis labels aligned under the chart area
                ft.Container(
                    padding=ft.padding.only(left=80),
                    content=x_axis_labels_row,
                ),
            ],
        ),
    )

    # Container containing all of the added assets.
    holdings = ft.Column(
        controls=[
            ft.Container(
                content=assets_column,
            )
        ],
    )

    # Content of the "Holding" container.
    content = ft.Container(
        width=900,
        content=ft.Column(
            spacing=24,
            controls=[
                header,
                graph,
                ft.Row(alignment=ft.MainAxisAlignment.CENTER),
                ft.Text(
                    "Holdings",
                    size=20,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                ),
                holdings,
            ],
        ),
    )

    page.add(
        ft.Container(
            alignment=ft.alignment.top_center,
            padding=ft.padding.symmetric(horizontal=16, vertical=24),
            content=content,
        )
    )
    refresh_assets()


# Start the Flet app with main as the target function.
ft.app(target=main)
