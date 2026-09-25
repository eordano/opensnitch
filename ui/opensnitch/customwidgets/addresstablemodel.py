
from PyQt6.QtSql import QSqlQuery

from opensnitch.utils import AsnDB, GeoDB
from opensnitch.customwidgets.generictableview import GenericTableModel
from PyQt6.QtCore import QCoreApplication as QC

class AddressTableModel(GenericTableModel):
    """Summary-view model that can append lookup columns (network name,
    country) computed from the IP found in one of the query's columns."""

    ENRICHERS = {
        "asn": (QC.translate("stats", "Network name", ""), lambda ip: AsnDB.instance().get_asn(ip)),
        "country": (QC.translate("stats", "Country", ""), lambda ip: GeoDB.instance().country(ip)),
    }

    def __init__(self, tableName, headerLabels):
        self.ipColumn = None
        self.enrichment = []
        super().__init__(tableName, headerLabels)
        self.asndb = AsnDB.instance()
        self.geodb = GeoDB.instance()

    def setEnrichment(self, ipColumn, keys):
        """ipColumn: index of the query column holding an IP, or None.
        keys: which ENRICHERS to append, in order."""
        keys = [k for k in keys if k in self.ENRICHERS]
        if ipColumn is None:
            keys = []
        changed = (ipColumn, keys) != (self.ipColumn, self.enrichment)
        self.ipColumn = ipColumn
        self.enrichment = keys
        if changed:
            self.lastItems = []
            self.setModelColumns(self.realQuery.record().count())
        return changed

    def enrichmentLabels(self):
        return [self.ENRICHERS[k][0] for k in self.enrichment]

    def lastQuery(self):
        return self.origQueryStr

    def update_col_count(self):
        queryColumns = self.realQuery.record().count()
        if queryColumns + len(self.enrichment) != self.lastColumnCount:
            self.setModelColumns(queryColumns)

    def setModelColumns(self, queryColumns):
        self.blockSignals(True)
        self.headerLabels = []
        self.removeColumns(0, self.lastColumnCount)
        self.setHorizontalHeaderLabels(self.headerLabels)
        for col in range(0, queryColumns):
            self.headerLabels.append(self.realQuery.record().fieldName(col))
        self.headerLabels.extend(self.enrichmentLabels())
        self.lastColumnCount = len(self.headerLabels)
        self.setHorizontalHeaderLabels(self.headerLabels)
        self.setColumnCount(self.lastColumnCount)
        self.blockSignals(False)
        # the view was not told about the column changes above; make it
        # re-read the column count so the header matches the rows.
        self.layoutChanged.emit()

    def fillVisibleRows(self, q, upperBound, force=False):
        super().fillVisibleRows(q, upperBound, force)
        if not self.enrichment or self.ipColumn is None:
            return
        for n, col in enumerate(self.items):
            if len(col) <= self.ipColumn:
                continue
            ip = col[self.ipColumn]
            extra = []
            for key in self.enrichment:
                try:
                    extra.append(self.ENRICHERS[key][1](ip))
                except Exception:
                    extra.append("")
            self.items[n] = col[:self.realQuery.record().count()] + extra
        self.lastItems = self.items
