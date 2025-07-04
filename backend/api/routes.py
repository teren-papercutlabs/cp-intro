import logging
from flask import Blueprint, jsonify, request
from backend.services import DataCollector, TradingAnalyzer
from backend.database.connection import get_db
from backend.models import Trader, TraderPerformance, Position, TradeOpportunity

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)

# Initialize services
data_collector = DataCollector()
analyzer = TradingAnalyzer()


@api_bp.route("/losers", methods=["GET"])
def get_top_losers():
    """Get top losing traders."""
    logger.info("GET /api/losers endpoint called")
    try:
        limit = request.args.get("limit", 500, type=int)
        logger.info(f"Requesting {limit} losers from data_collector")
        
        losers = data_collector.get_top_losers(limit=limit)
        
        logger.info(f"data_collector returned {len(losers)} losers")
        logger.info(f"Sample data: {losers[:2] if losers else 'No data'}")
        
        response = {
            "status": "success",
            "data": losers,
            "count": len(losers)
        }
        
        logger.info(f"Returning response with {len(losers)} items")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in /api/losers endpoint: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api_bp.route("/opportunities", methods=["GET"])
def get_opportunities():
    """Get current counter-trade opportunities."""
    try:
        opportunities = analyzer.get_active_opportunities()
        return jsonify({
            "status": "success",
            "data": opportunities,
            "count": len(opportunities)
        }), 200
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api_bp.route("/trader/<address>", methods=["GET"])
def get_trader_details(address: str):
    """Get detailed information about a specific trader."""
    try:
        with get_db() as db:
            trader = db.query(Trader).filter_by(address=address).first()
            
            if not trader:
                return jsonify({
                    "status": "error",
                    "message": "Trader not found"
                }), 404
            
            # Get recent performance
            recent_performance = db.query(TraderPerformance).filter_by(
                trader_id=trader.id
            ).order_by(TraderPerformance.date.desc()).limit(30).all()
            
            # Get open positions
            open_positions = db.query(Position).filter_by(
                trader_id=trader.id,
                status="OPEN"
            ).all()
            
            return jsonify({
                "status": "success",
                "data": {
                    "trader": {
                        "id": trader.id,
                        "address": trader.address,
                        "first_seen": trader.first_seen.isoformat(),
                        "last_updated": trader.last_updated.isoformat()
                    },
                    "performance": [
                        {
                            "date": perf.date.isoformat(),
                            "pnl_percentage": float(perf.pnl_percentage) if perf.pnl_percentage else 0,
                            "win_rate": float(perf.win_rate) if perf.win_rate else 0,
                            "total_trades": perf.total_trades
                        }
                        for perf in recent_performance
                    ],
                    "positions": [
                        {
                            "coin": pos.coin,
                            "side": pos.side,
                            "entry_price": float(pos.entry_price),
                            "size": float(pos.size),
                            "unrealized_pnl": float(pos.unrealized_pnl) if pos.unrealized_pnl else 0,
                            "opened_at": pos.opened_at.isoformat()
                        }
                        for pos in open_positions
                    ]
                }
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting trader details: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api_bp.route("/performance", methods=["GET"])
def get_system_performance():
    """Get overall system performance metrics."""
    try:
        with get_db() as db:
            # Count active traders
            active_traders = db.query(Trader).filter_by(is_active=True).count()
            
            # Count opportunities
            total_opportunities = db.query(TradeOpportunity).count()
            active_opportunities = db.query(TradeOpportunity).filter_by(status="ACTIVE").count()
            
            # Count positions
            open_positions = db.query(Position).filter_by(status="OPEN").count()
            
            return jsonify({
                "status": "success",
                "data": {
                    "active_traders": active_traders,
                    "total_opportunities": total_opportunities,
                    "active_opportunities": active_opportunities,
                    "open_positions": open_positions
                }
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting system performance: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api_bp.route("/collect/<address>", methods=["POST"])
def collect_trader_data(address: str):
    """Manually trigger data collection for a specific trader."""
    try:
        success = data_collector.collect_trader_data(address)
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Data collected for {address}"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to collect data for {address}"
            }), 500
            
    except Exception as e:
        logger.error(f"Error collecting data for {address}: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api_bp.route("/analyze", methods=["POST"])
def analyze_positions():
    """Manually trigger position analysis."""
    try:
        opportunities = analyzer.analyze_new_positions()
        
        return jsonify({
            "status": "success",
            "message": f"Analysis complete. Generated {len(opportunities)} opportunities.",
            "data": [
                {
                    "coin": opp.coin,
                    "loser_side": opp.loser_side,
                    "suggested_side": opp.suggested_side,
                    "confidence": float(opp.confidence_score)
                }
                for opp in opportunities
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error analyzing positions: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500