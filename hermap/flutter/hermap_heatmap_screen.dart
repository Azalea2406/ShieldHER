// hermap_heatmap_screen.dart
// HerMap — Live Risk Heatmap (Google Maps + colored zone circles)
// Requires: google_maps_flutter, http packages in pubspec.yaml

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:http/http.dart' as http;
import 'hermap_report_screen.dart'; // import your report screen

const String BASE_URL = 'http://10.0.2.2:8000';

// ── DATA MODEL ────────────────────────────────────────────────────────────
class RiskZone {
  final String zoneId;
  final double latitude;
  final double longitude;
  final double score;
  final int reportCount;
  final String riskLevel;

  RiskZone({
    required this.zoneId,
    required this.latitude,
    required this.longitude,
    required this.score,
    required this.reportCount,
    required this.riskLevel,
  });

  factory RiskZone.fromJson(Map<String, dynamic> json) => RiskZone(
        zoneId: json['zone_id'],
        latitude: json['latitude'].toDouble(),
        longitude: json['longitude'].toDouble(),
        score: json['score'].toDouble(),
        reportCount: json['report_count'],
        riskLevel: json['risk_level'],
      );

  Color get color {
    if (score < 40) return const Color(0xFF43A047); // green
    if (score < 70) return const Color(0xFFFB8C00); // orange
    return const Color(0xFFE53935);                  // red
  }

  double get radius => 80 + (score / 100) * 120; // 80–200m visual radius
}

// ── HEATMAP SCREEN ─────────────────────────────────────────────────────────
class HermapHeatmapScreen extends StatefulWidget {
  const HermapHeatmapScreen({super.key});

  @override
  State<HermapHeatmapScreen> createState() => _HermapHeatmapScreenState();
}

class _HermapHeatmapScreenState extends State<HermapHeatmapScreen> {
  GoogleMapController? _mapController;
  List<RiskZone> _zones = [];
  Set<Circle> _circles = {};
  Set<Marker> _markers = {};
  bool _loading = true;
  Timer? _refreshTimer;
  RiskZone? _selectedZone;

  // Default center: Hyderabad
  static const CameraPosition _initialCamera = CameraPosition(
    target: LatLng(17.3850, 78.4867),
    zoom: 14,
  );

  @override
  void initState() {
    super.initState();
    _fetchHeatmap();
    // Auto-refresh every 15 seconds
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) => _fetchHeatmap());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _mapController?.dispose();
    super.dispose();
  }

  // ── FETCH HEATMAP DATA ──────────────────────────────────────────────────
  Future<void> _fetchHeatmap() async {
    try {
      final response = await http.get(Uri.parse('$BASE_URL/heatmap'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final zones = (data['zones'] as List)
            .map((z) => RiskZone.fromJson(z))
            .toList();
        setState(() {
          _zones = zones;
          _circles = _buildCircles(zones);
          _markers = _buildMarkers(zones);
          _loading = false;
        });
      }
    } catch (e) {
      setState(() => _loading = false);
      debugPrint('HerMap fetch error: $e');
    }
  }

  // ── BUILD MAP CIRCLES ───────────────────────────────────────────────────
  Set<Circle> _buildCircles(List<RiskZone> zones) {
    return zones.map((zone) => Circle(
      circleId: CircleId(zone.zoneId),
      center: LatLng(zone.latitude, zone.longitude),
      radius: zone.radius,
      fillColor: zone.color.withOpacity(0.35),
      strokeColor: zone.color.withOpacity(0.7),
      strokeWidth: 2,
    )).toSet();
  }

  // ── BUILD MARKERS ───────────────────────────────────────────────────────
  Set<Marker> _buildMarkers(List<RiskZone> zones) {
    return zones
        .where((z) => z.riskLevel == 'high_risk') // only pin high-risk zones
        .map((zone) => Marker(
          markerId: MarkerId('marker_${zone.zoneId}'),
          position: LatLng(zone.latitude, zone.longitude),
          icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
          infoWindow: InfoWindow(
            title: '⚠️ High Risk Zone',
            snippet: 'Score: ${zone.score.toStringAsFixed(1)} | ${zone.reportCount} reports',
          ),
          onTap: () => setState(() => _selectedZone = zone),
        )).toSet();
  }

  // ── NAVIGATE TO REPORT ──────────────────────────────────────────────────
  void _openReportScreen(LatLng position) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportScreen(
          latitude: position.latitude,
          longitude: position.longitude,
        ),
      ),
    ).then((_) => _fetchHeatmap()); // refresh after report
  }

  // ── BUILD ────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1A2E),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.map_outlined, color: Color(0xFFD81B60), size: 22),
          SizedBox(width: 8),
          Text('HerMap', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
          SizedBox(width: 6),
          Text('Live', style: TextStyle(fontSize: 12, color: Color(0xFF43A047))),
        ]),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _fetchHeatmap,
            tooltip: 'Refresh',
          ),
        ],
        elevation: 0,
      ),
      body: Stack(
        children: [
          // ── Google Map ──
          GoogleMap(
            initialCameraPosition: _initialCamera,
            onMapCreated: (controller) => _mapController = controller,
            circles: _circles,
            markers: _markers,
            onLongPress: _openReportScreen, // long press to report at location
            mapType: MapType.normal,
            myLocationEnabled: true,
            myLocationButtonEnabled: false,
            zoomControlsEnabled: false,
          ),

          // ── Loading overlay ──
          if (_loading)
            Container(
              color: Colors.black54,
              child: const Center(child: CircularProgressIndicator(color: Color(0xFFD81B60))),
            ),

          // ── Legend ──
          Positioned(
            top: 16,
            right: 16,
            child: _buildLegend(),
          ),

          // ── Stats Bar ──
          Positioned(
            top: 16,
            left: 16,
            child: _buildStatsBar(),
          ),

          // ── Zone Detail Panel (bottom sheet style) ──
          if (_selectedZone != null)
            Positioned(
              bottom: 90,
              left: 16,
              right: 16,
              child: _buildZoneCard(_selectedZone!),
            ),

          // ── Refresh indicator ──
          Positioned(
            bottom: 16,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.black87,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Auto-refreshes every 15s · Long press map to report',
                  style: TextStyle(color: Colors.grey[400], fontSize: 11),
                ),
              ),
            ),
          ),
        ],
      ),

      // ── FAB: Report at current location ──
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openReportScreen(const LatLng(17.3850, 78.4867)),
        backgroundColor: const Color(0xFFD81B60),
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add_alert_outlined),
        label: const Text('Report Incident', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildLegend() {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.95),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 6)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Risk Level', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
          const SizedBox(height: 6),
          _legendRow(const Color(0xFF43A047), 'Safe (0–39)'),
          _legendRow(const Color(0xFFFB8C00), 'Caution (40–69)'),
          _legendRow(const Color(0xFFE53935), 'High Risk (70+)'),
        ],
      ),
    );
  }

  Widget _legendRow(Color color, String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(children: [
        Container(width: 14, height: 14, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11)),
      ]),
    );
  }

  Widget _buildStatsBar() {
    final highRisk = _zones.where((z) => z.riskLevel == 'high_risk').length;
    final caution = _zones.where((z) => z.riskLevel == 'caution').length;
    final totalReports = _zones.fold(0, (sum, z) => sum + z.reportCount);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E).withOpacity(0.92),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$totalReports reports active', style: const TextStyle(color: Colors.white70, fontSize: 11)),
          const SizedBox(height: 4),
          Row(children: [
            _statChip('${_zones.length}', 'zones', Colors.white54),
            const SizedBox(width: 8),
            _statChip('$highRisk', '⚠️ high', const Color(0xFFE53935)),
            const SizedBox(width: 8),
            _statChip('$caution', '⚡ caution', const Color(0xFFFB8C00)),
          ]),
        ],
      ),
    );
  }

  Widget _statChip(String value, String label, Color color) {
    return Column(children: [
      Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
      Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
    ]);
  }

  Widget _buildZoneCard(RiskZone zone) {
    return GestureDetector(
      onTap: () => setState(() => _selectedZone = null),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 10)],
        ),
        child: Row(children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(color: zone.color.withOpacity(0.15), shape: BoxShape.circle),
            child: Icon(Icons.location_on, color: zone.color, size: 26),
          ),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(zone.riskLevel.replaceAll('_', ' ').toUpperCase(),
                style: TextStyle(color: zone.color, fontWeight: FontWeight.bold, fontSize: 13)),
            Text('Score: ${zone.score.toStringAsFixed(1)}/100', style: const TextStyle(fontSize: 12)),
            Text('${zone.reportCount} community reports', style: TextStyle(fontSize: 11, color: Colors.grey[500])),
          ])),
          TextButton(
            onPressed: () => _openReportScreen(LatLng(zone.latitude, zone.longitude)),
            child: const Text('Report Here', style: TextStyle(color: Color(0xFFD81B60), fontSize: 12)),
          ),
        ]),
      ),
    );
  }
}
