// hermap_report_screen.dart
// HerMap — Anonymous Incident Report Submission
// Drop this file into your Flutter lib/ folder and call ReportScreen() from your router.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

// ── CONFIG ─────────────────────────────────────────────────────────────────
// Replace with your WSL IP when testing on Android emulator/device
// Run in WSL: ip addr show eth0 | grep "inet "
const String BASE_URL = 'http://10.0.2.2:8000'; // 10.0.2.2 = localhost for Android emulator

// ── INCIDENT TYPES ─────────────────────────────────────────────────────────
const List<Map<String, dynamic>> incidentTypes = [
  {'id': 'harassment',        'label': 'Harassment',         'icon': Icons.warning_amber_rounded,  'color': Color(0xFFE53935)},
  {'id': 'poor_lighting',     'label': 'Poor Lighting',      'icon': Icons.lightbulb_off_outlined, 'color': Color(0xFFFB8C00)},
  {'id': 'suspicious_person', 'label': 'Suspicious Person',  'icon': Icons.person_off_outlined,    'color': Color(0xFF8E24AA)},
  {'id': 'unsafe_area',       'label': 'Unsafe Area',        'icon': Icons.location_off_outlined,  'color': Color(0xFFD81B60)},
  {'id': 'crowding',          'label': 'Unsafe Crowding',    'icon': Icons.people_outline,         'color': Color(0xFF039BE5)},
  {'id': 'other',             'label': 'Other',              'icon': Icons.more_horiz_rounded,     'color': Color(0xFF546E7A)},
];

// ── MAIN SCREEN ────────────────────────────────────────────────────────────
class ReportScreen extends StatefulWidget {
  final double latitude;
  final double longitude;

  const ReportScreen({
    super.key,
    this.latitude = 17.3850,   // default to Hyderabad for demo
    this.longitude = 78.4867,
  });

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  String? _selectedType;
  int _severity = 5;
  final TextEditingController _descController = TextEditingController();
  bool _isSubmitting = false;
  bool _submitted = false;

  // ── SUBMIT REPORT ─────────────────────────────────────────────────────────
  Future<void> _submitReport() async {
    if (_selectedType == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an incident type')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final response = await http.post(
        Uri.parse('$BASE_URL/report'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'latitude': widget.latitude,
          'longitude': widget.longitude,
          'incident_type': _selectedType,
          'description': _descController.text.trim().isEmpty
              ? null
              : _descController.text.trim(),
          'severity': _severity,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() => _submitted = true);
        _showSuccessDialog(data['zone_id'], data['current_zone_score'].toDouble());
      } else {
        throw Exception('Server error ${response.statusCode}');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to submit: $e'), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => _isSubmitting = false);
    }
  }

  void _showSuccessDialog(String zoneId, double score) {
    final riskLevel = score < 40 ? 'Safe' : score < 70 ? 'Caution' : 'High Risk';
    final riskColor = score < 40 ? Colors.green : score < 70 ? Colors.orange : Colors.red;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Row(children: [
          Icon(Icons.check_circle, color: Color(0xFFD81B60), size: 28),
          SizedBox(width: 8),
          Text('Report Received', style: TextStyle(fontSize: 18)),
        ]),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Thank you for keeping your community safe.', style: TextStyle(fontSize: 14)),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: riskColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: riskColor.withOpacity(0.3)),
              ),
              child: Row(children: [
                Icon(Icons.location_on, color: riskColor, size: 20),
                const SizedBox(width: 8),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Zone Risk Level', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  Text(riskLevel, style: TextStyle(fontWeight: FontWeight.bold, color: riskColor, fontSize: 16)),
                  Text('Score: ${score.toStringAsFixed(1)}/100', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                ]),
              ]),
            ),
            if (score >= 70) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Row(children: [
                  Icon(Icons.local_police, color: Colors.red, size: 18),
                  SizedBox(width: 8),
                  Expanded(child: Text('Authorities have been automatically notified.', style: TextStyle(fontSize: 12, color: Colors.red))),
                ]),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () { Navigator.pop(context); Navigator.pop(context); },
            child: const Text('Done', style: TextStyle(color: Color(0xFFD81B60))),
          ),
        ],
      ),
    );
  }

  // ── BUILD ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F4F6),
      appBar: AppBar(
        backgroundColor: const Color(0xFFD81B60),
        foregroundColor: Colors.white,
        title: const Text('Report an Incident', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // ── Anonymous badge ──
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.green.shade200),
              ),
              child: const Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.shield_outlined, color: Colors.green, size: 16),
                SizedBox(width: 6),
                Text('100% Anonymous — no identity stored', style: TextStyle(fontSize: 12, color: Colors.green, fontWeight: FontWeight.w600)),
              ]),
            ),

            const SizedBox(height: 24),

            // ── Section: Incident Type ──
            const Text('What happened?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF2D2D2D))),
            const SizedBox(height: 12),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 2.8,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
              ),
              itemCount: incidentTypes.length,
              itemBuilder: (context, i) {
                final type = incidentTypes[i];
                final selected = _selectedType == type['id'];
                return GestureDetector(
                  onTap: () => setState(() => _selectedType = type['id']),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    decoration: BoxDecoration(
                      color: selected ? (type['color'] as Color).withOpacity(0.15) : Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: selected ? type['color'] as Color : Colors.grey.shade200,
                        width: selected ? 2 : 1,
                      ),
                    ),
                    child: Row(children: [
                      const SizedBox(width: 12),
                      Icon(type['icon'] as IconData, color: type['color'] as Color, size: 20),
                      const SizedBox(width: 8),
                      Expanded(child: Text(type['label'] as String, style: TextStyle(fontSize: 13, fontWeight: selected ? FontWeight.bold : FontWeight.normal, color: const Color(0xFF2D2D2D)))),
                    ]),
                  ),
                );
              },
            ),

            const SizedBox(height: 24),

            // ── Section: Severity ──
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              const Text('Severity', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF2D2D2D))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: _severityColor().withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(_severityLabel(), style: TextStyle(color: _severityColor(), fontWeight: FontWeight.bold, fontSize: 13)),
              ),
            ]),
            const SizedBox(height: 8),
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: _severityColor(),
                thumbColor: _severityColor(),
                overlayColor: _severityColor().withOpacity(0.2),
                inactiveTrackColor: Colors.grey.shade200,
              ),
              child: Slider(
                value: _severity.toDouble(),
                min: 1,
                max: 10,
                divisions: 9,
                onChanged: (v) => setState(() => _severity = v.round()),
              ),
            ),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Minor', style: TextStyle(fontSize: 11, color: Colors.grey[500])),
              Text('Critical', style: TextStyle(fontSize: 11, color: Colors.grey[500])),
            ]),

            const SizedBox(height: 24),

            // ── Section: Description (optional) ──
            const Text('Details (optional)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF2D2D2D))),
            const SizedBox(height: 8),
            TextField(
              controller: _descController,
              maxLines: 3,
              maxLength: 200,
              decoration: InputDecoration(
                hintText: 'Briefly describe what you observed...',
                hintStyle: TextStyle(color: Colors.grey[400], fontSize: 13),
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFFD81B60))),
                contentPadding: const EdgeInsets.all(14),
              ),
            ),

            const SizedBox(height: 28),

            // ── Submit Button ──
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : _submitReport,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFD81B60),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  elevation: 2,
                ),
                child: _isSubmitting
                    ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Icon(Icons.send_rounded, size: 20),
                        SizedBox(width: 8),
                        Text('Submit Report', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      ]),
              ),
            ),

            const SizedBox(height: 16),
            Center(
              child: Text('Your location is used only to score this zone.\nNo personal data is stored.', textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: Colors.grey[400])),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Color _severityColor() {
    if (_severity <= 3) return Colors.green;
    if (_severity <= 6) return Colors.orange;
    return Colors.red;
  }

  String _severityLabel() {
    if (_severity <= 3) return 'Low ($_severity/10)';
    if (_severity <= 6) return 'Medium ($_severity/10)';
    return 'High ($_severity/10)';
  }
}
